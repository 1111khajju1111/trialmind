"""Priority 3 -- Pharmacovigilance MVP: the safety-reporting "deadline
engine" plus shared constants for AE/SAE cases.

First-shot scope, deliberately simplified (see the implementation plan,
section 14 "What NOT to implement"): this is a *demonstrator* of
regulatory-timeline tracking, not a validated implementation of NDCT Rules
2019 / GCP-ASU / ICH E2A reporting timelines, and should never be described
as compliant. The shape (fatal/life-threatening SAEs on the shortest fuse,
other SAEs next, routine AEs last) mirrors the general accelerated-reporting
principle those frameworks share, so the demo timeline behaves the way a
reviewer familiar with pharmacovigilance would expect.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

SEVERITIES = ["mild", "moderate", "severe"]

SERIOUSNESS_OPTIONS = [
    "not_serious", "death", "life_threatening", "hospitalization", "disability", "other_serious",
]

OUTCOMES = ["recovered", "recovering", "not_recovered", "fatal", "unknown"]

CAUSALITIES = ["unrelated", "unlikely", "possible", "probable", "definite", "unassessed"]

STATUS_ORDER = ["draft", "under_review", "reported", "closed"]

# Fix #5: a single, reusable disclaimer string -- surfaced both in code
# comments (for a code reader) and in the API response of GET
# /safety/dashboard (for anyone consuming the API directly), so the
# "demonstrator, not validated" caveat travels with the data, not just the
# source file.
DEADLINE_DISCLAIMER = (
    "Report due dates are a first-shot demonstrator of accelerated safety "
    "reporting (24h for fatal/life-threatening SAEs, 7 days for other SAEs, "
    "15 days for routine AEs). They approximate the general principle "
    "shared by NDCT Rules 2019 / GCP-ASU / ICH E2A, are configurable, and "
    "have not been validated against a specific regulatory timeline. Do not "
    "treat them as a compliance determination."
)


def is_serious(seriousness: str) -> bool:
    return seriousness != "not_serious"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_due_date(event_date: datetime, seriousness: str) -> datetime:
    """Deadline engine: how long a coordinator has to get this case to
    'reported' status, counted from event_date.

    - Fatal / life-threatening SAE -> 24 hours (expedited initial report)
    - Other SAE (hospitalization / disability / other_serious) -> 7 days
    - Non-serious AE -> 15 days (routine/periodic reporting)
    """
    event_date = _aware(event_date)
    if seriousness in ("death", "life_threatening"):
        return event_date + timedelta(hours=24)
    if seriousness in ("hospitalization", "disability", "other_serious"):
        return event_date + timedelta(days=7)
    return event_date + timedelta(days=15)


def due_status(due_date: datetime | None, status: str, now: datetime | None = None) -> str | None:
    """'overdue' | 'approaching' | 'on_track', or None once a case has left
    the active-reporting states (reported/closed) -- an already-reported
    case isn't "overdue" just because its clock ran out before it was
    filed."""
    if not due_date or status in ("reported", "closed"):
        return None
    now = now or datetime.now(timezone.utc)
    due_date = _aware(due_date)
    if due_date < now:
        return "overdue"
    if due_date - now <= timedelta(hours=48):
        return "approaching"
    return "on_track"


def summarize(cases: list) -> dict:
    """Shared aggregation used by both the study-scoped and portfolio-wide
    safety dashboards, so the two never drift out of sync on definitions."""
    ae = [c for c in cases if not c.is_serious]
    sae = [c for c in cases if c.is_serious]
    open_cases = [c for c in cases if c.status not in ("reported", "closed")]
    overdue = [c for c in cases if due_status(c.report_due_date, c.status) == "overdue"]
    approaching = [c for c in cases if due_status(c.report_due_date, c.status) == "approaching"]

    trend = Counter()
    for c in cases:
        key = c.event_date.strftime("%Y-%m") if c.event_date else "unknown"
        trend[key] += 1
    monthly_trend = dict(sorted(trend.items())[-6:])

    return {
        "ae_count": len(ae),
        "sae_count": len(sae),
        "total_cases": len(cases),
        "open_cases": len(open_cases),
        "overdue_reports": len(overdue),
        "approaching_due_reports": len(approaching),
        "by_severity": dict(Counter(c.severity for c in cases)),
        "by_status": dict(Counter(c.status for c in cases)),
        "monthly_trend": monthly_trend,
    }
