"""Priority 4 -- Ethics + CTRI + Regulatory Compliance.

Evolves the Priority 1 StudyMilestone model into a "Regulatory Timeline"
without a schema change: milestone_type has always been a free-text column,
so new types (IEC Submission, CTRI Update, Amendment) just need to be used,
not migrated. What's new here is a second, finer-grained read on top of the
existing pending/completed/overdue `status` column: a tri-state
`due_status` (on_track / due_soon / overdue) so a coordinator sees what
needs attention *before* it's actually late -- the same on_track/
approaching/overdue idea Priority 3's deadline engine uses for AE/SAE
reporting, applied here to regulatory milestones with a longer, IEC/CTRI-
appropriate window instead of a clinical-safety clock.

GET /compliance/alerts (routers/compliance.py) and GET /dashboard/regulatory
(routers/dashboard.py) both build on `build_alerts()` here so the two never
disagree about what counts as an alert.
"""
from datetime import datetime, timedelta, timezone

# Informational for the frontend's milestone-type dropdown and for anyone
# reading the API. StudyMilestone.milestone_type stays free-text so this
# list can grow without a migration.
MILESTONE_TYPES = [
    "iec_submission", "iec_approval", "ctri_registration", "ctri_update",
    "amendment", "site_activation", "first_patient_in", "last_patient_in",
    "close_out", "other",
]

# Milestone types considered part of the "Ethics + CTRI" regulatory
# timeline proper, as distinct from operational milestones (site
# activation, first/last patient, close-out) that also live in
# StudyMilestone.
REGULATORY_MILESTONE_TYPES = [
    "iec_submission", "iec_approval", "ctri_registration", "ctri_update", "amendment",
]

CTRI_STATUSES = ["not_registered", "pending", "registered"]

# How many days out counts as "due soon" for a regulatory milestone --
# deliberately a longer, calmer window than Priority 3's AE/SAE 48-hour
# "approaching" flag: an IEC/CTRI action is planned weeks out, not run
# against a clinical safety clock. Configurable, not a validated
# regulatory requirement -- see DEADLINE_DISCLAIMER.
DUE_SOON_WINDOW_DAYS = 14

DEADLINE_DISCLAIMER = (
    "Regulatory due-soon/overdue flags are a first-shot demonstrator based on "
    "each milestone's planned_date and a configurable 14-day due-soon window. "
    "They approximate a general oversight principle (IEC/CTRI actions should "
    "be visible before they lapse) and are not a validated GCP-ASU/NDCT Rules "
    "2019/CTRI compliance determination."
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def milestone_due_status(milestone, now: datetime | None = None) -> str | None:
    """'overdue' | 'due_soon' | 'on_track', or None for a completed
    milestone or a pending one with no planned_date (nothing to alert on)."""
    if milestone.status == "completed" or milestone.actual_date:
        return None
    if not milestone.planned_date:
        return None
    now = now or datetime.now(timezone.utc)
    planned = _aware(milestone.planned_date)
    if planned < now:
        return "overdue"
    if planned - now <= timedelta(days=DUE_SOON_WINDOW_DAYS):
        return "due_soon"
    return "on_track"


def build_alerts(db) -> list[dict]:
    """Unified compliance alert feed: overdue/due-soon regulatory
    milestones, overdue AE/SAE safety reports, and flagged-overdue
    monitoring visits, all in one list sorted overdue-first. Only
    actionable items (due_soon/overdue) are included -- on_track items
    aren't alerts."""
    # Local imports to avoid a circular import (models doesn't need to know
    # about this service, but this service needs the models).
    from app import models
    from app.services import safety as safety_svc

    alerts: list[dict] = []

    studies_by_id = {s.id: s for s in db.query(models.Study).all()}

    milestones = db.query(models.StudyMilestone).all()
    for m in milestones:
        severity = milestone_due_status(m)
        if severity not in ("overdue", "due_soon"):
            continue
        study = studies_by_id.get(m.study_id)
        alerts.append({
            "type": "milestone",
            "subtype": m.milestone_type,
            "severity": severity,
            "study_id": m.study_id,
            "study_code": study.study_code if study else None,
            "study_title": study.title if study else None,
            "title": m.name,
            "due_date": m.planned_date,
            "detail": f"{m.milestone_type.replace('_', ' ').title()} \u2014 \"{m.name}\"",
        })

    safety_cases = db.query(models.SafetyCase).all()
    for c in safety_cases:
        severity = safety_svc.due_status(c.report_due_date, c.status)
        if severity not in ("overdue", "approaching"):
            continue
        study = studies_by_id.get(c.study_id)
        alerts.append({
            "type": "safety",
            "subtype": "sae" if c.is_serious else "ae",
            "severity": "due_soon" if severity == "approaching" else "overdue",
            "study_id": c.study_id,
            "study_code": study.study_code if study else None,
            "study_title": study.title if study else None,
            "title": c.event_term,
            "due_date": c.report_due_date,
            "detail": f"{'SAE' if c.is_serious else 'AE'} report due for case #{c.id}",
        })

    visits = db.query(models.MonitoringVisit).filter(models.MonitoringVisit.overdue.is_(True)).all()
    for v in visits:
        study = studies_by_id.get(v.study_id)
        alerts.append({
            "type": "monitoring",
            "subtype": "monitoring_visit",
            "severity": "overdue",
            "study_id": v.study_id,
            "study_code": study.study_code if study else None,
            "study_title": study.title if study else None,
            "title": "Monitoring visit",
            "due_date": v.visit_date,
            "detail": v.findings or "Monitoring visit flagged overdue.",
        })

    severity_rank = {"overdue": 0, "due_soon": 1}

    def _sort_key(a):
        due = a["due_date"]
        due = _aware(due) if due else datetime.max.replace(tzinfo=timezone.utc)
        return (severity_rank.get(a["severity"], 2), due)

    alerts.sort(key=_sort_key)
    return alerts
