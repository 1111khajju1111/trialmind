"""Priority 3 -- Pharmacovigilance MVP.

AE/SAE capture (patient/study/site/event/date/severity/seriousness/outcome),
a Draft -> Under Review -> Reported -> Closed case workflow, a simple
configurable causality assessment, the deadline engine (due-date calc +
approaching/overdue flags), and a safety dashboard (AE count, SAE count,
open cases, overdue reports, trend).

Every create/status-change action is also logged into the existing
AgentAction table (run_id="safety:{study_id}") -- the same lightweight
audit-trail pattern routers/studies.py uses -- so these actions already
show up via GET /audit/timeline/safety:{study_id} ahead of the dedicated
append-only AuditEvent model (Priority 5).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services import safety as safety_svc
from app.services import safety_signals as signal_svc
from app.rbac import require_role
import json

router = APIRouter(prefix="/safety", tags=["pharmacovigilance"], dependencies=[Depends(require_role())])


def _log(db: Session, study_id: int, step_name: str, detail: str):
    db.add(models.AgentAction(
        run_id=f"safety:{study_id}", trial_id=None, step_name=step_name, detail=detail,
    ))


def _get_study_or_404(db: Session, study_id: int) -> models.Study:
    study = db.query(models.Study).filter(models.Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found.")
    return study


def _case_out(db: Session, case: models.SafetyCase) -> dict:
    patient = db.query(models.Patient).filter(models.Patient.id == case.patient_id).first()
    site = db.query(models.Site).filter(models.Site.id == case.site_id).first() if case.site_id else None
    return {
        "id": case.id,
        "study_id": case.study_id,
        "site_id": case.site_id,
        "site_name": site.institution if site else None,
        "patient_id": case.patient_id,
        "patient_name": patient.name if patient else f"Patient #{case.patient_id}",
        "event_term": case.event_term,
        "event_date": case.event_date,
        "is_serious": case.is_serious,
        "severity": case.severity,
        "seriousness": case.seriousness,
        "outcome": case.outcome,
        "causality": case.causality,
        "status": case.status,
        "narrative": case.narrative,
        "report_due_date": case.report_due_date,
        "reported_date": case.reported_date,
        "due_status": safety_svc.due_status(case.report_due_date, case.status),
        "drug": case.drug,
        "batch_number": case.batch_number,
        "dose": case.dose,
        "route": case.route,
        "administration_date": case.administration_date,
        "location": case.location,
        "symptom_onset_date": case.symptom_onset_date,
        "action_taken": case.action_taken,
        "onset_latency_hours": safety_svc.onset_latency_hours(
            case.administration_date, case.symptom_onset_date
        ),
        "created_at": case.created_at,
    }


def _create_case(payload: schemas.SafetyCaseCreate, db: Session, *, require_serious: bool) -> models.SafetyCase:
    """require_serious=True is the strict /safety/sae entry point;
    require_serious=False is the strict /safety/adverse-events entry point.
    Fix #3 (strict AE/SAE endpoint semantics): each endpoint only accepts
    the seriousness class it advertises -- no silent downgrading/upgrading
    of what the caller asked to record."""
    _get_study_or_404(db, payload.study_id)

    patient = db.query(models.Patient).filter(models.Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="patient_id does not reference an existing patient.")

    # Fix #1: a safety case can only be recorded against a patient who is
    # actually a subject of this study -- an AE/SAE isn't meaningful (and
    # shouldn't be recordable) for someone who was never enrolled/screened
    # into the study's recruitment funnel in the first place.
    subject = db.query(models.StudySubject).filter(
        models.StudySubject.study_id == payload.study_id,
        models.StudySubject.patient_id == payload.patient_id,
    ).first()
    if not subject:
        raise HTTPException(
            status_code=400,
            detail=(
                "patient_id is not a StudySubject of this study. Add the patient to the "
                "study's recruitment funnel (Subjects tab) before recording a safety case "
                "for them."
            ),
        )

    if payload.site_id is not None:
        site = db.query(models.Site).filter(
            models.Site.id == payload.site_id, models.Site.study_id == payload.study_id
        ).first()
        if not site:
            raise HTTPException(status_code=400, detail="site_id does not reference a site on this study.")

    event_term = payload.event_term.strip()
    if not event_term:
        raise HTTPException(status_code=400, detail="event_term is required.")

    seriousness = payload.seriousness
    if require_serious and seriousness == "not_serious":
        raise HTTPException(
            status_code=400,
            detail=(
                "POST /safety/sae requires a serious criterion (death, life_threatening, "
                "hospitalization, disability, or other_serious). Use POST /safety/adverse-events "
                "for a non-serious AE."
            ),
        )
    if not require_serious and seriousness != "not_serious":
        raise HTTPException(
            status_code=400,
            detail=(
                "POST /safety/adverse-events only accepts seriousness='not_serious'. "
                "Use POST /safety/sae to record a serious adverse event."
            ),
        )

    event_date = payload.event_date or datetime.now(timezone.utc)
    due = safety_svc.compute_due_date(event_date, seriousness)

    case = models.SafetyCase(
        study_id=payload.study_id,
        site_id=payload.site_id,
        patient_id=payload.patient_id,
        event_term=event_term,
        event_date=event_date,
        is_serious=safety_svc.is_serious(seriousness),
        severity=payload.severity,
        seriousness=seriousness,
        outcome=payload.outcome,
        causality=payload.causality,
        narrative=payload.narrative,
        status="draft",
        report_due_date=due,
        drug=payload.drug,
        batch_number=payload.batch_number,
        dose=payload.dose,
        route=payload.route,
        administration_date=payload.administration_date,
        location=payload.location,
        symptom_onset_date=payload.symptom_onset_date,
        action_taken=payload.action_taken,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    kind = "SAE" if case.is_serious else "AE"
    _log(db, payload.study_id, "safety_case_created",
         f"{kind} recorded for patient #{case.patient_id} ({event_term[:120]}). "
         f"Report due {due.strftime('%Y-%m-%d %H:%M UTC')}.")
    db.commit()
    return case


# ---------- Adverse Events (strictly non-serious) ----------

@router.post("/adverse-events", dependencies=[Depends(require_role("Pharmacovigilance", "Study Coordinator"))])
def create_adverse_event(payload: schemas.SafetyCaseCreate, db: Session = Depends(get_db)):
    case = _create_case(payload, db, require_serious=False)
    return _case_out(db, case)


@router.get("/adverse-events")
def list_adverse_events(
    study_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)
):
    query = db.query(models.SafetyCase).filter(models.SafetyCase.is_serious.is_(False))
    if study_id is not None:
        query = query.filter(models.SafetyCase.study_id == study_id)
    if status is not None:
        query = query.filter(models.SafetyCase.status == status)
    cases = query.order_by(models.SafetyCase.id.desc()).all()
    return [_case_out(db, c) for c in cases]


# ---------- Serious Adverse Events (strictly serious) ----------

@router.post("/sae", dependencies=[Depends(require_role("Pharmacovigilance", "Study Coordinator"))])
def create_sae(payload: schemas.SafetyCaseCreate, db: Session = Depends(get_db)):
    case = _create_case(payload, db, require_serious=True)
    return _case_out(db, case)


@router.get("/sae")
def list_sae(study_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.SafetyCase).filter(models.SafetyCase.is_serious.is_(True))
    if study_id is not None:
        query = query.filter(models.SafetyCase.study_id == study_id)
    if status is not None:
        query = query.filter(models.SafetyCase.status == status)
    cases = query.order_by(models.SafetyCase.id.desc()).all()
    return [_case_out(db, c) for c in cases]


# ---------- Individual case / status workflow ----------

@router.get("/cases/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.SafetyCase).filter(models.SafetyCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Safety case not found.")
    return _case_out(db, case)


@router.patch("/cases/{case_id}/status", dependencies=[Depends(require_role("Pharmacovigilance"))])
def update_case_status(case_id: int, payload: schemas.SafetyCaseStatusUpdate, db: Session = Depends(get_db)):
    """Fix #2: strictly sequential Draft -> Under Review -> Reported ->
    Closed. Not just "no going backward" -- a case must pass through every
    intermediate status in order (no skipping straight from Draft to
    Reported), matching a real pharmacovigilance case workflow where each
    stage is a distinct, auditable review step. Re-submitting the current
    status is a no-op rather than an error."""
    case = db.query(models.SafetyCase).filter(models.SafetyCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Safety case not found.")

    order = safety_svc.STATUS_ORDER
    current_rank = order.index(case.status) if case.status in order else 0
    new_rank = order.index(payload.status)

    if new_rank == current_rank:
        return _case_out(db, case)
    if new_rank < current_rank:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move status backward from '{case.status}' to '{payload.status}'.",
        )
    if new_rank != current_rank + 1:
        expected = order[current_rank + 1]
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot skip statuses: case is '{case.status}' and must move to "
                f"'{expected}' next, not '{payload.status}'."
            ),
        )

    prev_status = case.status
    case.status = payload.status
    if payload.status == "reported" and not case.reported_date:
        case.reported_date = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)

    _log(db, case.study_id, "safety_case_status_changed",
         f"Case #{case.id} ({case.event_term[:80]}) moved {prev_status} -> {payload.status}.")
    db.commit()

    return _case_out(db, case)


# ---------- Safety dashboard ----------

@router.get("/dashboard")
def safety_dashboard(study_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.SafetyCase)
    if study_id is not None:
        query = query.filter(models.SafetyCase.study_id == study_id)
    cases = query.order_by(models.SafetyCase.id.desc()).all()

    summary = safety_svc.summarize(cases)
    summary["cases"] = [_case_out(db, c) for c in cases[:200]]
    # Fix #5: keep the configurable-deadline disclaimer visible at the API
    # boundary too, not just in code comments -- anyone consuming this
    # endpoint directly (frontend, judges' API walkthrough, another
    # service) sees the same caveat the docstring gives a code reader.
    summary["deadline_disclaimer"] = safety_svc.DEADLINE_DISCLAIMER
    return summary


# ---------- Safety Signal Engine (Priority 3(b)) ----------

def _signal_out(db: Session, signal: models.SafetySignal) -> dict:
    site = db.query(models.Site).filter(models.Site.id == signal.site_id).first() if signal.site_id else None
    case_ids = json.loads(signal.case_ids) if signal.case_ids else []
    return {
        "id": signal.id,
        "study_id": signal.study_id,
        "site_id": signal.site_id,
        "site_name": site.institution if site else None,
        "signal_key": signal.signal_key,
        "drug": signal.drug,
        "batch_number": signal.batch_number,
        "window_start": signal.window_start,
        "window_end": signal.window_end,
        "case_ids": case_ids,
        "patient_count": signal.patient_count,
        "case_count": signal.case_count,
        "symptom_similarity": signal.symptom_similarity,
        "site_concentration": signal.site_concentration,
        "location_concentration": signal.location_concentration,
        "dominant_location": signal.dominant_location,
        "confidence_score": signal.confidence_score,
        "severity_score": signal.severity_score,
        "rationale": signal.rationale,
        "status": signal.status,
        "reviewed_by": signal.reviewed_by,
        "review_notes": signal.review_notes,
        "reviewed_at": signal.reviewed_at,
        "created_at": signal.created_at,
        "updated_at": signal.updated_at,
        "disclaimer": signal_svc.SIGNAL_DISCLAIMER,
    }


@router.post("/signals/detect", dependencies=[Depends(require_role("Pharmacovigilance"))])
def detect_signals(payload: schemas.SafetySignalDetectRequest, db: Session = Depends(get_db)):
    """Runs the correlation engine over drug+batch+time clusters in scope
    and creates/updates SafetySignal rows. Does not touch escalated or
    dismissed signals -- those are frozen human decisions."""
    if payload.study_id is not None:
        _get_study_or_404(db, payload.study_id)

    signals = signal_svc.detect_signals(
        db, study_id=payload.study_id, window_hours=payload.window_hours, min_patients=payload.min_patients,
    )

    scope = f"study #{payload.study_id}" if payload.study_id is not None else "all studies"
    log_study_id = payload.study_id if payload.study_id is not None else 0
    _log(db, log_study_id, "safety_signal_detection_run",
         f"Signal detection run over {scope} (window={payload.window_hours}h, "
         f"min_patients={payload.min_patients}): {len(signals)} signal(s) open or updated.")
    db.commit()

    return {"signals_detected": len(signals), "signals": [_signal_out(db, s) for s in signals]}


@router.get("/signals")
def list_signals(study_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.SafetySignal)
    if study_id is not None:
        query = query.filter(models.SafetySignal.study_id == study_id)
    if status is not None:
        query = query.filter(models.SafetySignal.status == status)
    signals = query.order_by(models.SafetySignal.confidence_score.desc(), models.SafetySignal.id.desc()).all()
    return [_signal_out(db, s) for s in signals]


@router.get("/signals/{signal_id}")
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    signal = db.query(models.SafetySignal).filter(models.SafetySignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Safety signal not found.")
    out = _signal_out(db, signal)
    case_ids = out["case_ids"]
    cases = db.query(models.SafetyCase).filter(models.SafetyCase.id.in_(case_ids)).all() if case_ids else []
    out["cases"] = [_case_out(db, c) for c in cases]
    return out


@router.patch("/signals/{signal_id}/status", dependencies=[Depends(require_role("Pharmacovigilance"))])
def update_signal_status(
    signal_id: int, payload: schemas.SafetySignalStatusUpdate, db: Session = Depends(get_db),
):
    """Human review workflow: open -> under_review is required first (a PV
    officer must look before deciding), then under_review branches to
    escalated or dismissed. Both are terminal -- re-detection will never
    modify a signal again after this. No skipping straight from open to a
    terminal state, matching the 'signal must be reviewed before it's
    acted on' principle from the module docstring."""
    signal = db.query(models.SafetySignal).filter(models.SafetySignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Safety signal not found.")

    if signal.status in signal_svc.TERMINAL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Signal #{signal.id} is already '{signal.status}', a terminal review decision.",
        )

    new_status = payload.status
    if signal.status == "open" and new_status not in ("under_review",):
        raise HTTPException(
            status_code=400,
            detail="An 'open' signal must move to 'under_review' first, before escalating or dismissing.",
        )
    if signal.status == "under_review" and new_status not in ("escalated", "dismissed"):
        raise HTTPException(
            status_code=400,
            detail="A signal 'under_review' can only move to 'escalated' or 'dismissed'.",
        )

    prev_status = signal.status
    signal.status = new_status
    if new_status in signal_svc.TERMINAL_STATUSES or new_status == "under_review":
        signal.reviewed_by = "demo_user"  # matches ApprovalLog.actor's demo-scope pattern
        if payload.review_notes:
            signal.review_notes = payload.review_notes
        signal.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(signal)

    _log(db, signal.study_id, "safety_signal_status_changed",
         f"Signal #{signal.id} ({signal.drug}/{signal.batch_number}) moved {prev_status} -> {new_status}.")
    db.commit()

    return _signal_out(db, signal)
