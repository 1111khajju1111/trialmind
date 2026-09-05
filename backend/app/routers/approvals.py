from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, auth
from app.services.recruitment import sync_subject_from_match
from app.rbac import require_role

router = APIRouter(prefix="/approvals", tags=["approvals"], dependencies=[Depends(require_role())])

MODEL_MAP = {
    "patient_matching": models.PatientMatch,
    "regulatory": models.RegulatoryDraft,
}

# Fallback actor label for approvals made without a logged-in session --
# only reachable when settings.demo_mode allows the legacy header-only
# path (see app/rbac.py), e.g. the existing test suite. A real logged-in
# user is now attributed by username (see submit_approval below), not
# hard-coded, now that /auth/login exists.
DEMO_ACTOR = "demo_coordinator"


@router.post("/", dependencies=[Depends(require_role("Principal Investigator", "Study Coordinator"))])
def submit_approval(
    req: schemas.ApprovalRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    model_cls = MODEL_MAP.get(req.module)
    if not model_cls:
        return {"error": f"Unknown module '{req.module}'."}

    record = db.query(model_cls).filter(model_cls.id == req.record_id).first()
    if not record:
        return {"error": "Record not found."}

    # Safety boundary: a deterministically NOT_ELIGIBLE candidate can never
    # be approved, no matter what the UI allows -- this is the server-side
    # gate, not just a UI affordance. (VERIFICATION_REQUIRED candidates CAN
    # still be approved -- that's the human-in-the-loop path for cases the
    # deterministic engine couldn't fully resolve on its own.)
    if (
        req.module == "patient_matching"
        and req.action == "approved"
        and getattr(record, "verdict", None) == "NOT_ELIGIBLE"
    ):
        return {"error": "This candidate does not meet trial criteria (NOT_ELIGIBLE) and cannot be approved."}

    # Idempotency / contradiction guard: once a record has been decided,
    # further approve/reject calls are rejected rather than silently
    # overwriting the audit trail with conflicting actions.
    if record.status in ("approved", "rejected"):
        if record.status == req.action:
            return {"ok": True, "note": "Already in this state; no change made."}
        return {"error": f"Cannot {req.action} a record that is already {record.status}."}

    record.status = req.action
    db.add(record)

    # Priority 2: the audit trail entry captures not just who decided what
    # and when, but *why* -- the AI's own rationale for the recommendation
    # being reviewed, plus the reviewer's note if they gave one (e.g. why
    # they overrode a VERIFICATION_REQUIRED verdict).
    ai_rationale = getattr(record, "rationale", None)
    labeled_parts = [
        (label, text.strip())
        for label, text in (("AI rationale", ai_rationale), ("Reviewer note", req.reviewer_note))
        if text and text.strip()
    ]
    rationale = " | ".join(f"{label}: {text}" for label, text in labeled_parts) or None

    # Attribute this decision to the actual logged-in user rather than a
    # hard-coded placeholder, now that /auth/login exists. Falls back to
    # DEMO_ACTOR only when there's no valid session -- reachable solely via
    # the demo_mode header-only fallback (see app/rbac.py), e.g. the
    # existing test suite that doesn't call /auth/login.
    session = auth.session_from_authorization_header(authorization)
    actor = session["username"] if session else DEMO_ACTOR

    log = models.ApprovalLog(
        module=req.module,
        record_id=req.record_id,
        action=req.action,
        actor=actor,
        rationale=rationale,
    )
    db.add(log)
    db.commit()

    if req.module == "patient_matching" and req.action == "approved":
        # Wire the approved AI recommendation into the CTMS recruitment
        # funnel (Priority 1) it was scoped to (Priority 2).
        sync_subject_from_match(db, record)

    return {"ok": True}


@router.get("/log")
def get_log(db: Session = Depends(get_db)):
    logs = db.query(models.ApprovalLog).order_by(models.ApprovalLog.id.desc()).limit(50).all()
    return [
        {
            "id": l.id, "module": l.module, "record_id": l.record_id,
            "action": l.action, "actor": l.actor,
            "rationale": l.rationale,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in logs
    ]
