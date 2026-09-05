"""GET /dashboard/portfolio -- CTMS-level executive KPIs across all studies.

Priority 1 (studies, sites, milestones, deviations, monitoring visits,
subjects) plus Priority 3 (AE/SAE, overdue safety reports) are reported for
real here. Data-quality queries is still a later priority and is reported
as explicit not-yet-available rather than a faked zero that would look
like a real "no issues" reading.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.services import safety as safety_svc
from app.services import compliance as compliance_svc
from app.rbac import require_role

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_role())])


@router.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    studies = db.query(models.Study).all()
    milestones = db.query(models.StudyMilestone).all()
    deviations = db.query(models.ProtocolDeviation).all()
    visits = db.query(models.MonitoringVisit).all()

    now = datetime.now(timezone.utc)
    overdue_milestones = 0
    for m in milestones:
        if m.status == "overdue":
            overdue_milestones += 1
        elif m.status == "pending" and m.planned_date:
            planned = m.planned_date if m.planned_date.tzinfo else m.planned_date.replace(tzinfo=timezone.utc)
            if planned < now:
                overdue_milestones += 1

    active_studies = [s for s in studies if s.status == "active"]
    recruitment_lag_studies = sum(
        1 for s in active_studies
        if s.target_enrollment and s.enrolled_count < 0.5 * s.target_enrollment
    )

    safety_cases = db.query(models.SafetyCase).all()
    safety_summary = safety_svc.summarize(safety_cases)

    # Priority 2 SIH polish: the "Control Tower" single-screen view needs
    # open safety *signals* (Safety Signal Engine clusters, distinct from
    # open safety *cases* above) plus regulatory/monitoring alert counts,
    # split out of the same compliance.build_alerts() feed the Regulatory
    # page uses so the two views can never disagree on what counts as an
    # alert.
    open_safety_signals = db.query(models.SafetySignal).filter(
        models.SafetySignal.status.in_(["open", "under_review"])
    ).count()
    compliance_alerts = compliance_svc.build_alerts(db)
    regulatory_alert_count = sum(1 for a in compliance_alerts if a["type"] == "milestone")
    monitoring_alert_count = sum(1 for a in compliance_alerts if a["type"] == "monitoring")

    return {
        "active_studies": len(active_studies),
        "total_studies": len(studies),
        "total_enrolled": sum(s.enrolled_count for s in studies),
        "total_enrollment_target": sum(s.target_enrollment or 0 for s in studies),
        "recruitment_lag_studies": recruitment_lag_studies,
        "pending_iec_ctri_actions": overdue_milestones,
        "open_protocol_deviations": sum(1 for d in deviations if d.resolution_status != "resolved"),
        "overdue_monitoring_visits": sum(1 for v in visits if v.overdue),
        "ae_count": safety_summary["ae_count"],
        "sae_count": safety_summary["sae_count"],
        "open_safety_cases": safety_summary["open_cases"],
        "overdue_safety_reports": safety_summary["overdue_reports"],
        "approaching_due_safety_reports": safety_summary["approaching_due_reports"],
        "open_safety_signals": open_safety_signals,
        "regulatory_alert_count": regulatory_alert_count,
        "monitoring_alert_count": monitoring_alert_count,
        "safety_module_available": True,
        # Not yet implemented -- the data-quality module (Priority 3 table
        # also lists "Data-quality queries" but it isn't part of the
        # pharmacovigilance MVP). Surfaced explicitly so the UI can show
        # "coming soon" instead of a misleading 0.
        "data_quality_module_available": False,
        "studies": [
            {
                "id": s.id,
                "study_code": s.study_code,
                "title": s.title,
                "status": s.status,
                "phase": s.phase,
                "enrolled_count": s.enrolled_count,
                "target_enrollment": s.target_enrollment,
            }
            for s in studies
        ],
    }


@router.get("/regulatory")
def get_regulatory_dashboard(db: Session = Depends(get_db)):
    """Priority 4 -- portfolio-wide Ethics + CTRI + Regulatory Compliance
    view: CTRI registration status across studies, regulatory-milestone
    counts by due_status, amendment activity, and the top compliance
    alerts (shared with GET /compliance/alerts via
    services/compliance.py:build_alerts so the two never disagree)."""
    studies = db.query(models.Study).all()
    milestones = db.query(models.StudyMilestone).all()

    ctri_counts = {"not_registered": 0, "pending": 0, "registered": 0}
    for s in studies:
        ctri_counts[s.ctri_status or "not_registered"] = ctri_counts.get(s.ctri_status or "not_registered", 0) + 1

    regulatory_milestones = [m for m in milestones if m.milestone_type in compliance_svc.REGULATORY_MILESTONE_TYPES]
    due_counts = {"on_track": 0, "due_soon": 0, "overdue": 0, "completed": 0}
    for m in regulatory_milestones:
        if m.status == "completed" or m.actual_date:
            due_counts["completed"] += 1
            continue
        ds = compliance_svc.milestone_due_status(m)
        if ds:
            due_counts[ds] += 1

    amendments_logged = sum(1 for m in milestones if m.milestone_type == "amendment")

    alerts = compliance_svc.build_alerts(db)

    return {
        "total_studies": len(studies),
        "ctri_status_counts": ctri_counts,
        "regulatory_milestones_on_track": due_counts["on_track"],
        "regulatory_milestones_due_soon": due_counts["due_soon"],
        "regulatory_milestones_overdue": due_counts["overdue"],
        "regulatory_milestones_completed": due_counts["completed"],
        "amendments_logged": amendments_logged,
        "alerts": alerts[:20],
        "total_alert_count": len(alerts),
        "deadline_disclaimer": compliance_svc.DEADLINE_DISCLAIMER,
    }
