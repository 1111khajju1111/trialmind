from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/timeline/{run_id}")
def get_timeline(run_id: str, db: Session = Depends(get_db)):
    """Returns every step the agent took during one run, in order --
    powers the 'AI action timeline' UI from the project review."""
    actions = db.query(models.AgentAction).filter(
        models.AgentAction.run_id == run_id
    ).order_by(models.AgentAction.id.asc()).all()
    return [
        {
            "id": a.id, "step_name": a.step_name, "detail": a.detail,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in actions
    ]


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    """Lists distinct agent run IDs with their trial and start time, most
    recent first -- used to populate a run picker in the UI."""
    starts = db.query(models.AgentAction).filter(
        models.AgentAction.step_name == "run_started"
    ).order_by(models.AgentAction.id.desc()).all()
    return [
        {
            "run_id": a.run_id, "trial_id": a.trial_id,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "detail": a.detail,
        }
        for a in starts
    ]
