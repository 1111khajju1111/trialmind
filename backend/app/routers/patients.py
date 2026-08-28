import json
import re
import uuid
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app import models, schemas
from app.services.groq_client import ask_llm
from app.services.agent_orchestrator import run_agent
import resend
from pydantic import BaseModel, EmailStr
from app.config import settings

router = APIRouter(prefix="/patients", tags=["patient-matching"])

OUTREACH_SYSTEM_PROMPT = (
    "You draft short, professional physician outreach messages for clinical "
    "trial coordinators. The patient has already been approved by a human "
    "coordinator as a trial candidate -- your job is only to draft the message, "
    "not to make any eligibility judgment."
)


@router.get("/", response_model=list[schemas.PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.query(models.Patient).all()


def _outreach_status(m: models.PatientMatch) -> str | None:
    """DRAFT / FINALIZED / SENT -- FINALIZED means the coordinator locked in
    the draft (the demo-mode terminal state, always DRAFT -- NOT SENT in
    practice); SENT means a real email actually went out via Resend."""
    if not m.outreach_draft:
        return None
    if not getattr(m, "outreach_sent", False):
        return "DRAFT"
    return "SENT" if getattr(m, "email_transmitted", False) else "FINALIZED"


def _serialize_match(m: models.PatientMatch) -> dict:
    return {
        "id": m.id,
        "patient_id": m.patient_id,
        "trial_id": m.trial_id,
        "study_id": m.study_id,
        "site_id": m.site_id,
        "run_id": m.run_id,
        "fit_score": m.fit_score,
        "verdict": m.verdict,
        "rationale": m.rationale,
        "outreach_draft": m.outreach_draft,
        "status": m.status,
        "criteria_results": json.loads(m.criteria_results) if m.criteria_results else [],
        "missing_info": json.loads(m.missing_info) if m.missing_info else [],
        "outreach_sent": bool(getattr(m, "outreach_sent", False)),
        "outreach_status": _outreach_status(m),
        "email_transmitted": bool(getattr(m, "email_transmitted", False)),
        "evidence": json.loads(m.evidence) if m.evidence else [],
    }


def _persist_matches(
    db: Session, trial_id: int, run_id: str, eligibility_cache: dict,
    evidence_cache: dict, rationales: dict,
    study_id: int | None = None, site_id: int | None = None,
):
    created = []
    for pid, elig in eligibility_cache.items():
        patient = db.query(models.Patient).filter(models.Patient.id == pid).first()
        if not patient:
            continue
        evidence = evidence_cache.get(pid, [])
        rationale = rationales.get(pid) or (
            "No evidence was retrieved for this patient; verdict is based on "
            "deterministic criteria checks only." if not evidence else
            "Agent did not provide a rationale for this patient."
        )
        match = models.PatientMatch(
            patient_id=pid, trial_id=trial_id, study_id=study_id, site_id=site_id,
            run_id=run_id,
            fit_score=elig["score"], verdict=elig["verdict"], rationale=rationale,
            outreach_draft="", criteria_results=json.dumps(elig["results"]),
            missing_info=json.dumps(elig["missing_fields"]), evidence=json.dumps(evidence),
            status="pending_review",
        )
        db.add(match)
        created.append(match)
    db.commit()
    return created


def _background_run(trial_id: int, run_id: str, allowed_patient_ids: set | None, study_id: int | None, site_id: int | None):
    """Runs the agent workflow in the background so the HTTP response can
    return the run_id immediately, letting the frontend poll the timeline
    for live progress instead of blocking on one long request.

    P0 fix: matches are persisted and the write is confirmed BEFORE
    run_completed is logged. Previously the agent logged run_completed as
    soon as it produced final text, which raced with persistence -- a
    frontend poll landing in that gap would show a "completed" run with
    zero candidates. Now the sequence is strictly:
    agent finishes -> persist matches -> confirm write -> log run_completed
    (or log a failure event if persistence fails)."""
    db = SessionLocal()
    try:
        trial = db.query(models.Trial).filter(models.Trial.id == trial_id).first()
        if not trial:
            return
        _, final_text, eligibility_cache, evidence_cache, agent_error = run_agent(
            db, trial, run_id=run_id, allowed_patient_ids=allowed_patient_ids
        )
        if agent_error:
            return  # error already logged to AgentAction by run_agent

        cleaned = re.sub(r"^```json|```$", "", final_text.strip(), flags=re.MULTILINE).strip()
        try:
            rationales = {r["patient_id"]: r["rationale"] for r in json.loads(cleaned)}
        except (json.JSONDecodeError, KeyError, TypeError):
            rationales = {}

        try:
            created = _persist_matches(
                db, trial_id, run_id, eligibility_cache, evidence_cache, rationales,
                study_id=study_id, site_id=site_id,
            )
            # Confirm the write actually landed before declaring completion.
            confirmed = db.query(models.PatientMatch).filter(
                models.PatientMatch.run_id == run_id
            ).count()
            if confirmed != len(created):
                db.add(models.AgentAction(
                    run_id=run_id, trial_id=trial_id, step_name="persistence_failed",
                    detail=f"Expected {len(created)} matches, found {confirmed} after commit."))
                db.commit()
                return
        except Exception as e:
            db.rollback()
            db.add(models.AgentAction(
                run_id=run_id, trial_id=trial_id, step_name="persistence_failed",
                detail=f"Failed to save matches: {e}"))
            db.commit()
            return

        db.add(models.AgentAction(
            run_id=run_id, trial_id=trial_id, step_name="run_completed",
            detail=f"Run complete -- {len(created)} candidate(s) persisted, awaiting human review."))
        db.commit()
    finally:
        db.close()


@router.post("/match/start")
def start_matching(req: schemas.MatchRunRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Kicks off an agent run in the background and returns immediately with
    a run_id. Poll GET /audit/timeline/{run_id} for live progress, and
    GET /patients/matches?run_id=... once you see a 'run_completed' step.

    Priority 2 (corrected direction): the candidate pool comes from the
    Patient directory (by condition), NOT from StudySubject -- a patient
    must never need to already be a StudySubject of this study to be
    considered by the AI. That was circular (StudySubject -> pool -> AI).
    The correct direction is:

        Patient pool -> AI -> human approval -> StudySubject

    study_id/site_id are still resolved and validated here, but only as the
    *destination* recorded on each PatientMatch -- where a StudySubject will
    be created if a coordinator approves the recommendation (see
    approvals.py / services/recruitment.sync_subject_from_match). They do
    not filter who the AI is allowed to evaluate.
    """
    trial = db.query(models.Trial).filter(models.Trial.id == req.trial_id).first()
    if not trial:
        return {"error": "Trial not found."}

    study_id = trial.study_id
    site_id = None

    if study_id is not None and req.site_id is not None:
        site = db.query(models.Site).filter(
            models.Site.id == req.site_id, models.Site.study_id == study_id
        ).first()
        if not site:
            return {"error": "site_id does not reference a site on this trial's study."}
        site_id = req.site_id
    elif study_id is None and req.site_id is not None:
        return {"error": "site_id was provided but this trial isn't linked to a study."}

    patient_count = db.query(models.Patient).filter(models.Patient.condition == trial.condition).count()
    if not patient_count:
        return {"error": f"No patients found matching condition '{trial.condition}'."}

    if not trial.structured_criteria or trial.structured_criteria == "[]":
        return {"error": "This trial has no extracted eligibility criteria. Re-upload the protocol."}

    try:
        criteria_check = json.loads(trial.structured_criteria)
    except json.JSONDecodeError:
        return {"error": "This trial's stored criteria are corrupted. Re-upload the protocol."}
    if not criteria_check:
        return {"error": "This trial has no extracted eligibility criteria. Re-upload the protocol."}

    run_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(_background_run, trial.id, run_id, None, study_id, site_id)
    return {"run_id": run_id, "status": "started", "study_id": study_id, "site_id": site_id}


@router.get("/matches")
def list_matches(run_id: str = None, db: Session = Depends(get_db)):
    query = db.query(models.PatientMatch)
    if run_id:
        query = query.filter(models.PatientMatch.run_id == run_id)
    matches = query.order_by(models.PatientMatch.fit_score.desc()).all()
    return [_serialize_match(m) for m in matches]


@router.post("/matches/{match_id}/outreach")
def generate_outreach(match_id: int, db: Session = Depends(get_db)):
    """Generates the outreach draft. Only callable after human approval --
    the hard human-in-the-loop gate. Idempotent: returns the existing draft
    if one was already generated rather than regenerating it."""
    match = db.query(models.PatientMatch).filter(models.PatientMatch.id == match_id).first()
    if not match:
        return {"error": "Match not found."}
    if match.status != "approved":
        return {"error": "This candidate must be approved before an outreach draft can be generated."}
    if match.outreach_draft:
        return _serialize_match(match)

    patient = db.query(models.Patient).filter(models.Patient.id == match.patient_id).first()
    trial = db.query(models.Trial).filter(models.Trial.id == match.trial_id).first()

    prompt = (
        f"Patient: {patient.name}, age {patient.age}, condition {patient.condition}. "
        f"Trial: {trial.name}. Approved rationale: {match.rationale}. "
        f"Draft a short outreach message to the referring physician."
    )
    try:
        draft = ask_llm(OUTREACH_SYSTEM_PROMPT, prompt, max_tokens=400)
    except Exception as e:
        return {"error": f"Outreach generation failed: {e}"}

    match.outreach_draft = draft
    db.add(match)
    db.commit()
    db.refresh(match)
    return _serialize_match(match)

class SendOutreachRequest(BaseModel):
    to_email: EmailStr
    subject: str | None = None
    custom_draft: str | None = None

    class Config:
        extra = "forbid"


@router.post("/matches/{match_id}/send-outreach")
def send_outreach(
    match_id: int,
    body: SendOutreachRequest,
    db: Session = Depends(get_db)
):
    match = (
        db.query(models.PatientMatch)
        .filter(models.PatientMatch.id == match_id)
        .first()
    )

    if not match:
        return {"error": "Match not found."}

    if match.status != "approved":
        return {
            "error": "Only approved candidates can have outreach sent."
        }

    if not match.outreach_draft:
        return {
            "error": "Generate the outreach draft first."
        }

    if match.outreach_sent:
        return {
            "error": "Outreach has already been sent.",
            "match": _serialize_match(match)
        }

    patient = (
        db.query(models.Patient)
        .filter(models.Patient.id == match.patient_id)
        .first()
    )

    trial = (
        db.query(models.Trial)
        .filter(models.Trial.id == match.trial_id)
        .first()
    )

    # --------------------------------------------------
    # Use edited draft if provided, otherwise original
    # --------------------------------------------------
    email_body = (
        body.custom_draft.strip()
        if body.custom_draft and body.custom_draft.strip()
        else match.outreach_draft
    )

    to_email = str(body.to_email)

    subject = (
        body.subject
        or f"Clinical Trial Candidate Referral – "
           f"{trial.name if trial else 'Trial'}"
    )

    # --------------------------------------------------
    # DEMO MODE -- also forced whenever settings.demo_mode is true, even if
    # a real Resend key happens to be configured. A hackathon demo should
    # never be one misconfigured env var away from actually emailing a
    # (synthetic) patient record.
    # --------------------------------------------------
    if settings.demo_mode or not settings.resend_api_key:

        match.outreach_sent = True
        match.email_transmitted = False
        # Persist the coordinator's edited version here too, so the finalized
        # text shown afterward matches what they actually approved -- the
        # real-send branch below does this; demo mode should behave the same.
        match.outreach_draft = email_body

        db.add(match)

        db.add(
            models.AgentAction(
                run_id=match.run_id or "manual",
                trial_id=match.trial_id,
                step_name="outreach_sent",
                detail=(
                    f"[DEMO MODE] Outreach draft for patient "
                    f"#{match.patient_id} finalized (addressed to {to_email}). "
                    "DRAFT -- NOT SENT: no real email was transmitted."
                ),
            )
        )

        db.commit()
        db.refresh(match)

        return {
            "message": (
                f"DRAFT -- NOT SENT. Outreach for {to_email} is ready and recorded "
                "for coordinator review (demo mode: real email sending is disabled)."
            ),
            "match": _serialize_match(match),
        }

    # --------------------------------------------------
    # SEND USING RESEND
    # --------------------------------------------------
    try:
        resend.api_key = settings.resend_api_key

        resend.Emails.send(
            {
                "from": settings.resend_from,
                "to": [to_email],
                "subject": subject,
                "text": email_body,
            }
        )

    except Exception as e:
        return {
            "error": f"Failed to send email via Resend: {str(e)}"
        }

    # --------------------------------------------------
    # Mark as sent + audit
    # --------------------------------------------------
    match.outreach_sent = True
    match.email_transmitted = True
    match.outreach_draft = email_body

    db.add(match)

    db.add(
        models.AgentAction(
            run_id=match.run_id or "manual",
            trial_id=match.trial_id,
            step_name="outreach_sent",
            detail=(
                f"Outreach for patient #{match.patient_id} "
                f"({patient.name if patient else ''}) "
                f"sent to {to_email} via Resend"
            ),
        )
    )

    db.commit()
    db.refresh(match)

    return {
        "message": f"Outreach successfully sent to {to_email}",
        "match": _serialize_match(match),
    }