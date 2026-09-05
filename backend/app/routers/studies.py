"""Priority 1 — Core CTMS.

Study / Site / Milestone / Protocol Deviation / Monitoring Visit management,
scoped so the existing TrialMind protocol + eligibility + matching pipeline
can be attached to a Study via Trial.study_id (Priority 2 wires that up on
the trials/patients side).

Every create action is also logged into the existing AgentAction table
(reused as a lightweight audit trail, run_id="study:{study_id}") so these
actions already show up via GET /audit/timeline/study:{id} ahead of the
dedicated append-only AuditEvent model (Priority 5).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services.recruitment import recompute_recruitment
from app.services import compliance as compliance_svc
from app.rbac import require_role

# Router-level auth: every /studies/* route requires an authenticated
# session (any role) at minimum -- previously only the mutating endpoints
# individually declared require_role(), which left every GET (including
# study/subject listings) reachable with no auth at all. Endpoints that
# need a *specific* role beyond "logged in" still declare their own
# require_role("...") below; that stacks fine on top of this.
router = APIRouter(prefix="/studies", tags=["studies"], dependencies=[Depends(require_role())])

MAX_CODE_LEN = 50
MAX_TITLE_LEN = 300


def _log(db: Session, study_id: int, step_name: str, detail: str):
    db.add(models.AgentAction(
        run_id=f"study:{study_id}",
        trial_id=None,
        step_name=step_name,
        detail=detail,
    ))


def _get_study_or_404(db: Session, study_id: int) -> models.Study:
    study = db.query(models.Study).filter(models.Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found.")
    return study


def _mark_overdue_milestones(db: Session, study_id: int):
    """Flip pending milestones with a planned_date in the past to 'overdue'.
    Called on read so the status is always current without a background job."""
    now = datetime.now(timezone.utc)
    milestones = db.query(models.StudyMilestone).filter(
        models.StudyMilestone.study_id == study_id,
        models.StudyMilestone.status == "pending",
        models.StudyMilestone.planned_date.isnot(None),
    ).all()
    changed = False
    for m in milestones:
        planned = m.planned_date
        if planned.tzinfo is None:
            planned = planned.replace(tzinfo=timezone.utc)
        if planned < now:
            m.status = "overdue"
            changed = True
    if changed:
        db.commit()


# ---------- Study ----------

@router.post("/", response_model=schemas.StudyOut)
def create_study(payload: schemas.StudyCreate, db: Session = Depends(get_db)):
    code = payload.study_code.strip()
    title = payload.title.strip()
    if not code or len(code) > MAX_CODE_LEN:
        raise HTTPException(status_code=400, detail=f"study_code must be 1-{MAX_CODE_LEN} characters.")
    if not title or len(title) > MAX_TITLE_LEN:
        raise HTTPException(status_code=400, detail=f"title must be 1-{MAX_TITLE_LEN} characters.")
    if db.query(models.Study).filter(models.Study.study_code == code).first():
        raise HTTPException(status_code=400, detail=f"A study with code '{code}' already exists.")

    trial = None
    if payload.trial_id is not None:
        trial = db.query(models.Trial).filter(models.Trial.id == payload.trial_id).first()
        if not trial:
            raise HTTPException(status_code=404, detail="trial_id does not reference an existing trial.")
        if trial.study_id is not None:
            raise HTTPException(status_code=400, detail="That trial is already linked to a study.")

    study = models.Study(
        study_code=code,
        title=title,
        phase=payload.phase,
        intervention=payload.intervention,
        principal_investigator=payload.principal_investigator,
        target_enrollment=payload.target_enrollment or 0,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status or "planning",
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    if trial is not None:
        trial.study_id = study.id

    _log(db, study.id, "study_created", f"Study '{study.title}' ({study.study_code}) created.")
    db.commit()
    return study


@router.get("/", response_model=list[schemas.StudyOut])
def list_studies(db: Session = Depends(get_db)):
    return db.query(models.Study).order_by(models.Study.id.desc()).all()


@router.get("/{study_id}")
def get_study(study_id: int, db: Session = Depends(get_db)):
    study = _get_study_or_404(db, study_id)
    _mark_overdue_milestones(db, study_id)
    trial = db.query(models.Trial).filter(models.Trial.study_id == study_id).first()
    sites = db.query(models.Site).filter(models.Site.study_id == study_id).all()
    milestones = db.query(models.StudyMilestone).filter(models.StudyMilestone.study_id == study_id).all()
    deviations = db.query(models.ProtocolDeviation).filter(models.ProtocolDeviation.study_id == study_id).all()
    subjects = db.query(models.StudySubject).filter(models.StudySubject.study_id == study_id).all()
    return {
        "study": schemas.StudyOut.model_validate(study),
        "linked_trial": {"id": trial.id, "name": trial.name} if trial else None,
        "site_count": len(sites),
        "activated_site_count": sum(1 for s in sites if s.activation_status == "activated"),
        "open_deviation_count": sum(1 for d in deviations if d.resolution_status != "resolved"),
        "overdue_milestone_count": sum(1 for m in milestones if m.status == "overdue"),
        "subject_count": len(subjects),
    }


@router.patch("/{study_id}/recruitment", response_model=schemas.StudyOut)
def update_recruitment(study_id: int, payload: schemas.RecruitmentUpdate, db: Session = Depends(get_db)):
    """Manual override for studies with no StudySubject records yet. Once a
    study has subjects, recompute_recruitment() overwrites these counters
    on every subject create/update, so a manual PATCH here will be
    superseded the next time a subject changes."""
    study = _get_study_or_404(db, study_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None and value < 0:
            raise HTTPException(status_code=400, detail=f"{field} cannot be negative.")
        setattr(study, field, value)
    db.commit()
    db.refresh(study)
    _log(db, study.id, "recruitment_updated", f"Recruitment counts updated: {updates}")
    db.commit()
    return study


# ---------- Priority 4: CTRI registration + regulatory timeline ----------

@router.patch("/{study_id}/ctri", response_model=schemas.StudyOut, dependencies=[Depends(require_role("Ethics Committee", "Study Coordinator"))])
def update_ctri(study_id: int, payload: schemas.CTRIUpdate, db: Session = Depends(get_db)):
    """Update CTRI registration number/status/date. When a study is marked
    'registered' with a registration date, this also creates or updates the
    matching 'ctri_registration' StudyMilestone so the CTRI fields and the
    regulatory timeline never drift apart -- a coordinator filling in CTRI
    details here shouldn't also have to remember to log a milestone."""
    study = _get_study_or_404(db, study_id)
    updates = payload.model_dump(exclude_unset=True)

    if "ctri_status" in updates and updates["ctri_status"] is not None:
        if updates["ctri_status"] not in compliance_svc.CTRI_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"ctri_status must be one of {compliance_svc.CTRI_STATUSES}.",
            )

    for field, value in updates.items():
        setattr(study, field, value)
    db.commit()
    db.refresh(study)

    if study.ctri_status == "registered":
        milestone = db.query(models.StudyMilestone).filter(
            models.StudyMilestone.study_id == study_id,
            models.StudyMilestone.milestone_type == "ctri_registration",
        ).first()
        actual = study.ctri_registration_date or datetime.now(timezone.utc)
        if milestone:
            milestone.actual_date = actual
            milestone.status = "completed"
        else:
            db.add(models.StudyMilestone(
                study_id=study_id, milestone_type="ctri_registration",
                name=f"CTRI Registration{f' ({study.ctri_number})' if study.ctri_number else ''}",
                actual_date=actual, status="completed",
            ))
        db.commit()

    _log(db, study.id, "ctri_updated", f"CTRI fields updated: {updates}")
    db.commit()
    db.refresh(study)
    return study


@router.get("/{study_id}/regulatory-timeline")
def regulatory_timeline(study_id: int, db: Session = Depends(get_db)):
    """The 'evolve StudyMilestone into a Regulatory Timeline' view: every
    milestone on this study plus a computed on_track/due_soon/overdue read,
    alongside the study's CTRI registration fields."""
    study = _get_study_or_404(db, study_id)
    _mark_overdue_milestones(db, study_id)
    milestones = db.query(models.StudyMilestone).filter(
        models.StudyMilestone.study_id == study_id
    ).all()
    # Sort in Python rather than via SQL boolean-ordering tricks (dialect
    # behavior for "NULLs last" differs between SQLite and Postgres) --
    # milestones with a planned_date come first, chronologically, then
    # undated ones.
    def _sort_key(m):
        pd = m.planned_date
        if pd is None:
            return (True, datetime.max.replace(tzinfo=timezone.utc))
        if pd.tzinfo is None:
            pd = pd.replace(tzinfo=timezone.utc)
        return (False, pd)

    milestones.sort(key=_sort_key)

    items = []
    summary = {"on_track": 0, "due_soon": 0, "overdue": 0, "completed": 0}
    for m in milestones:
        due_status = compliance_svc.milestone_due_status(m)
        if m.status == "completed" or m.actual_date:
            summary["completed"] += 1
        elif due_status:
            summary[due_status] += 1
        items.append({
            "id": m.id,
            "milestone_type": m.milestone_type,
            "name": m.name,
            "planned_date": m.planned_date,
            "actual_date": m.actual_date,
            "status": m.status,
            "due_status": due_status,
            "is_regulatory": m.milestone_type in compliance_svc.REGULATORY_MILESTONE_TYPES,
        })

    return {
        "study_id": study.id,
        "study_code": study.study_code,
        "title": study.title,
        "ctri_number": study.ctri_number,
        "ctri_status": study.ctri_status or "not_registered",
        "ctri_registration_date": study.ctri_registration_date,
        "milestones": items,
        "summary": summary,
        "milestone_types": compliance_svc.MILESTONE_TYPES,
        "deadline_disclaimer": compliance_svc.DEADLINE_DISCLAIMER,
    }


# ---------- Sites ----------

@router.post("/{study_id}/sites", response_model=schemas.SiteOut)
def create_site(study_id: int, payload: schemas.SiteCreate, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    institution = payload.institution.strip()
    if not institution:
        raise HTTPException(status_code=400, detail="institution is required.")
    site = models.Site(
        study_id=study_id,
        site_code=payload.site_code,
        institution=institution,
        pi_name=payload.pi_name,
        coordinator_name=payload.coordinator_name,
        activation_status=payload.activation_status or "pending",
        enrollment_target=payload.enrollment_target or 0,
        activated_date=payload.activated_date,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    _log(db, study_id, "site_created", f"Site '{site.institution}' added.")
    db.commit()
    return site


@router.get("/{study_id}/sites", response_model=list[schemas.SiteOut])
def list_sites(study_id: int, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    return db.query(models.Site).filter(models.Site.study_id == study_id).all()


# ---------- Milestones ----------

@router.post("/{study_id}/milestones", response_model=schemas.MilestoneOut)
def create_milestone(study_id: int, payload: schemas.MilestoneCreate, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    milestone = models.StudyMilestone(
        study_id=study_id,
        milestone_type=payload.milestone_type,
        name=payload.name,
        planned_date=payload.planned_date,
        actual_date=payload.actual_date,
        status="completed" if payload.actual_date else (payload.status or "pending"),
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    _log(db, study_id, "milestone_created", f"Milestone '{milestone.name}' ({milestone.milestone_type}) recorded.")
    db.commit()
    return milestone


@router.get("/{study_id}/milestones", response_model=list[schemas.MilestoneOut])
def list_milestones(study_id: int, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    _mark_overdue_milestones(db, study_id)
    return db.query(models.StudyMilestone).filter(models.StudyMilestone.study_id == study_id).all()


# ---------- Protocol deviations ----------

@router.post("/{study_id}/deviations", response_model=schemas.DeviationOut)
def create_deviation(study_id: int, payload: schemas.DeviationCreate, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    description = payload.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="description is required.")
    deviation = models.ProtocolDeviation(
        study_id=study_id,
        site_id=payload.site_id,
        description=description,
        severity=payload.severity or "minor",
        deviation_date=payload.deviation_date,
        resolution_status=payload.resolution_status or "open",
    )
    db.add(deviation)
    db.commit()
    db.refresh(deviation)
    _log(db, study_id, "deviation_recorded", f"Protocol deviation recorded ({deviation.severity}): {description[:120]}")
    db.commit()
    return deviation


@router.get("/{study_id}/deviations", response_model=list[schemas.DeviationOut])
def list_deviations(study_id: int, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    return db.query(models.ProtocolDeviation).filter(models.ProtocolDeviation.study_id == study_id).all()


# ---------- Monitoring visits ----------

@router.post("/{study_id}/monitoring-visits", response_model=schemas.MonitoringVisitOut)
def create_monitoring_visit(study_id: int, payload: schemas.MonitoringVisitCreate, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    visit = models.MonitoringVisit(
        study_id=study_id,
        site_id=payload.site_id,
        visit_date=payload.visit_date,
        findings=payload.findings,
        overdue=payload.overdue or False,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    _log(db, study_id, "monitoring_visit_recorded", "Monitoring visit recorded.")
    db.commit()
    return visit


@router.get("/{study_id}/monitoring-visits", response_model=list[schemas.MonitoringVisitOut])
def list_monitoring_visits(study_id: int, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    return db.query(models.MonitoringVisit).filter(models.MonitoringVisit.study_id == study_id).all()


# ---------- Study Subjects (Patient -> StudySubject -> Site) ----------

def _subject_out(db: Session, subject: models.StudySubject) -> dict:
    """Enriches a StudySubject row with the patient name and site institution
    so the frontend doesn't need N+1 lookups to render a usable list."""
    patient = db.query(models.Patient).filter(models.Patient.id == subject.patient_id).first()
    site = db.query(models.Site).filter(models.Site.id == subject.site_id).first() if subject.site_id else None
    return {
        "id": subject.id,
        "study_id": subject.study_id,
        "site_id": subject.site_id,
        "site_name": site.institution if site else None,
        "patient_id": subject.patient_id,
        "patient_name": patient.name if patient else f"Patient #{subject.patient_id}",
        "subject_code": subject.subject_code,
        "status": subject.status,
        "enrolled_date": subject.enrolled_date,
        "notes": subject.notes,
        "consent_status": subject.consent_status or "not_obtained",
        "consent_version": subject.consent_version,
        "consent_date": subject.consent_date,
    }


@router.post("/{study_id}/subjects")
def create_subject(study_id: int, payload: schemas.StudySubjectCreate, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)

    patient = db.query(models.Patient).filter(models.Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="patient_id does not reference an existing patient.")

    if payload.site_id is not None:
        site = db.query(models.Site).filter(
            models.Site.id == payload.site_id, models.Site.study_id == study_id
        ).first()
        if not site:
            raise HTTPException(status_code=400, detail="site_id does not reference a site on this study.")

    existing = db.query(models.StudySubject).filter(
        models.StudySubject.study_id == study_id,
        models.StudySubject.patient_id == payload.patient_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This patient is already a subject on this study.")

    subject = models.StudySubject(
        study_id=study_id,
        site_id=payload.site_id,
        patient_id=payload.patient_id,
        subject_code=payload.subject_code,
        status=payload.status or "screened",
        enrolled_date=payload.enrolled_date,
        notes=payload.notes,
        consent_status=payload.consent_status or "not_obtained",
        consent_version=payload.consent_version,
        consent_date=payload.consent_date,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    recompute_recruitment(db, study_id)
    _log(db, study_id, "subject_added",
         f"Patient '{patient.name}' added to study as subject (status: {subject.status}).")
    db.commit()
    db.refresh(subject)
    return _subject_out(db, subject)


@router.get("/{study_id}/subjects")
def list_subjects(study_id: int, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    subjects = db.query(models.StudySubject).filter(
        models.StudySubject.study_id == study_id
    ).order_by(models.StudySubject.id.asc()).all()
    return [_subject_out(db, s) for s in subjects]


@router.patch("/{study_id}/subjects/{subject_id}")
def update_subject(study_id: int, subject_id: int, payload: schemas.StudySubjectUpdate, db: Session = Depends(get_db)):
    _get_study_or_404(db, study_id)
    subject = db.query(models.StudySubject).filter(
        models.StudySubject.id == subject_id, models.StudySubject.study_id == study_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found on this study.")

    if payload.site_id is not None:
        site = db.query(models.Site).filter(
            models.Site.id == payload.site_id, models.Site.study_id == study_id
        ).first()
        if not site:
            raise HTTPException(status_code=400, detail="site_id does not reference a site on this study.")

    updates = payload.model_dump(exclude_unset=True)
    prev_status = subject.status
    prev_consent = subject.consent_status
    for field, value in updates.items():
        setattr(subject, field, value)
    db.commit()
    db.refresh(subject)

    recompute_recruitment(db, study_id)
    if "status" in updates and updates["status"] != prev_status:
        _log(db, study_id, "subject_status_changed",
             f"Subject #{subject.id} moved {prev_status} -> {subject.status}.")
    if "consent_status" in updates and updates["consent_status"] != prev_consent:
        _log(db, study_id, "consent_status_changed",
             f"Subject #{subject.id} consent moved {prev_consent} -> {subject.consent_status}.")
    db.commit()
    db.refresh(subject)
    return _subject_out(db, subject)


@router.post("/{study_id}/subjects/{subject_id}/enroll", dependencies=[Depends(require_role("Principal Investigator", "Study Coordinator"))])
def enroll_subject(study_id: int, subject_id: int, payload: schemas.EnrollSubjectRequest, db: Session = Depends(get_db)):
    """Explicit enrollment transition (Priority 2):

        AI Approved -> Eligible -> [Enroll Patient] -> Enrolled

    A dedicated action rather than a generic status PATCH so "enrolling a
    patient" is a distinct, auditable clinical decision -- it can only be
    performed from "eligible" (an AI-approved recommendation, or a subject
    manually marked eligible), never as an arbitrary jump from any status,
    and it stamps enrolled_date the moment it happens.
    """
    _get_study_or_404(db, study_id)
    subject = db.query(models.StudySubject).filter(
        models.StudySubject.id == subject_id, models.StudySubject.study_id == study_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found on this study.")

    if subject.status != "eligible":
        raise HTTPException(
            status_code=400,
            detail=f"Only an eligible subject can be enrolled (current status: '{subject.status}').",
        )

    # Priority 6 -- Consent & Data Protection MVP. Informed consent must be
    # on record before enrollment; this is the one place consent_status
    # becomes an enforced gate rather than just a display field, matching
    # GCP/DPDP practice (consent precedes any study procedure).
    if subject.consent_status != "obtained":
        raise HTTPException(
            status_code=400,
            detail="Informed consent must be recorded as 'obtained' before this subject can be enrolled.",
        )

    subject.status = "enrolled"
    subject.enrolled_date = payload.enrolled_date or datetime.now(timezone.utc)
    db.commit()
    db.refresh(subject)

    recompute_recruitment(db, study_id)
    _log(db, study_id, "subject_enrolled", f"Subject #{subject.id} enrolled.")
    db.commit()
    db.refresh(subject)
    return _subject_out(db, subject)
