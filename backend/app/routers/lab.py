from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/lab", tags=["lab-scheduling"])


@router.get("/samples", response_model=list[schemas.SampleOut])
def list_samples(db: Session = Depends(get_db)):
    # Priority ordering mimics the agent's dynamic rescheduling logic:
    # urgent/breached samples surface first regardless of original queue order.
    samples = db.query(models.Sample).all()
    priority_rank = {"urgent": 0, "high": 1, "normal": 2}
    samples.sort(key=lambda s: (
        0 if s.breach_alert else 1,
        priority_rank.get(s.priority, 3),
    ))
    return samples


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db)):
    breached = db.query(models.Sample).filter(models.Sample.breach_alert == True).all()  # noqa: E712
    return [
        {
            "sample_id": s.id,
            "label": s.label,
            "message": (
                f"Storage breach: {s.label} is at {s.storage_temp_c}C, "
                f"required {s.required_temp_c}C. Immediate action needed."
            ),
        }
        for s in breached
    ]


@router.get("/equipment")
def list_equipment(db: Session = Depends(get_db)):
    return db.query(models.LabEquipment).all()
