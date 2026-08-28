from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app import models, mock_data
from app.rbac import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset", dependencies=[Depends(require_role("Administrator"))])
def reset_demo_data(db: Session = Depends(get_db)):
    """Wipes all data and reseeds the standard demo dataset (GLYCO-3,
    ARTHRIX-1, LIPID-2, ARTHRIX-2, GLYCO-4, and LIPID-3 trials with their
    patients). For repeatable hackathon demo runs -- call this between
    presentation run-throughs to return to a known, deterministic state
    without redeploying.

    This is a destructive, unauthenticated endpoint by design -- it's only
    ever safe to expose while settings.demo_mode is true. Deploying this
    with real patient data requires either disabling demo_mode (which
    disables this route entirely) or putting real authentication in front
    of it; there is no such thing as a safe "reset everything" button in
    a production system handling real records."""
    if not settings.demo_mode:
        raise HTTPException(
            status_code=403,
            detail="Demo reset is disabled outside demo mode.",
        )

    # Delete in FK-safe order
    db.query(models.ApprovalLog).delete()
    db.query(models.AgentAction).delete()
    db.query(models.PatientMatch).delete()
    db.query(models.RegulatoryDraft).delete()
    db.query(models.Sample).delete()
    db.query(models.LabEquipment).delete()
    db.query(models.ProtocolChunk).delete()
    db.query(models.MonitoringVisit).delete()
    db.query(models.ProtocolDeviation).delete()
    db.query(models.StudyMilestone).delete()
    db.query(models.StudySubject).delete()
    db.query(models.Site).delete()
    db.query(models.Trial).delete()
    db.query(models.Study).delete()
    db.query(models.Patient).delete()
    db.commit()

    mock_data.seed_if_empty(db)
    return {"ok": True, "message": "Demo data reset to initial seeded state."}
