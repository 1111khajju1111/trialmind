"""Priority 4 -- Ethics + CTRI + Regulatory Compliance.

GET /compliance/alerts is the unified alert feed documented in the SIH26046
first-shot API groups: overdue/due-soon regulatory milestones (IEC/CTRI/
amendments), overdue AE/SAE safety reports, and flagged monitoring visits,
all in one place instead of three tabs a coordinator has to check
separately.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import compliance as compliance_svc
from app.rbac import require_role

router = APIRouter(prefix="/compliance", tags=["compliance"], dependencies=[Depends(require_role())])


@router.get("/alerts")
def get_alerts(study_id: int | None = None, db: Session = Depends(get_db)):
    alerts = compliance_svc.build_alerts(db)
    if study_id is not None:
        alerts = [a for a in alerts if a["study_id"] == study_id]
    overdue = sum(1 for a in alerts if a["severity"] == "overdue")
    due_soon = sum(1 for a in alerts if a["severity"] == "due_soon")
    return {
        "alerts": alerts,
        "overdue_count": overdue,
        "due_soon_count": due_soon,
        "total_count": len(alerts),
        "deadline_disclaimer": compliance_svc.DEADLINE_DISCLAIMER,
    }
