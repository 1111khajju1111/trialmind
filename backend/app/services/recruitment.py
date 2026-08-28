"""Derives a Study's recruitment funnel counters from its StudySubject rows.

The funnel is cumulative: reaching a later stage implies having passed
earlier ones (an "enrolled" subject was necessarily screened and eligible
first), so each count includes every status at-or-beyond it. "withdrawn" is
a terminal side-branch and is counted separately, not folded into the
funnel stages.

Shared by routers/studies.py (called after every subject create/update) and
mock_data.py (called once after seeding demo subjects), so the derivation
logic lives in exactly one place.
"""
from app import models

STAGE_ORDER = ["screened", "eligible", "enrolled", "randomized", "completed"]

# Priority 2: how an AI patient-match verdict maps onto the CTMS recruitment
# funnel status once a human approves it. NOT_ELIGIBLE can never reach here
# (approvals.py already blocks approving a NOT_ELIGIBLE match), so it's
# deliberately absent from this map.
_VERDICT_TO_SUBJECT_STATUS = {
    "ELIGIBLE": "eligible",
    "POTENTIAL_MATCH": "eligible",
    "VERIFICATION_REQUIRED": "eligible",
}


def sync_subject_from_match(db, match: "models.PatientMatch") -> None:
    """Called when a coordinator approves an AI-generated patient match
    (Priority 2 human-in-the-loop gate). Links the AI recommendation into
    the CTMS recruitment funnel: creates the StudySubject if this patient
    isn't already tracked on the study, or advances their status to
    "eligible" if they're still earlier in the funnel. Never moves a subject
    backwards (e.g. won't downgrade an already-"enrolled" subject).

    No-ops if the match has no study_id (legacy trial with no study link) --
    there is nothing in the CTMS funnel to sync to in that case.
    """
    if not match.study_id:
        return

    new_status = _VERDICT_TO_SUBJECT_STATUS.get(match.verdict)
    if not new_status:
        return

    subject = db.query(models.StudySubject).filter(
        models.StudySubject.study_id == match.study_id,
        models.StudySubject.patient_id == match.patient_id,
    ).first()

    if subject is None:
        subject = models.StudySubject(
            study_id=match.study_id,
            site_id=match.site_id,
            patient_id=match.patient_id,
            status=new_status,
            notes=f"Added via AI patient-matching run {match.run_id or ''} (match #{match.id}).".strip(),
        )
        db.add(subject)
    else:
        current_rank = STAGE_ORDER.index(subject.status) if subject.status in STAGE_ORDER else -1
        new_rank = STAGE_ORDER.index(new_status)
        if new_rank > current_rank:
            subject.status = new_status
        if subject.site_id is None and match.site_id is not None:
            subject.site_id = match.site_id

    db.commit()
    recompute_recruitment(db, match.study_id)


def recompute_recruitment(db, study_id: int) -> None:
    subjects = db.query(models.StudySubject).filter(
        models.StudySubject.study_id == study_id
    ).all()

    # "screened" is the funnel entry point: every subject on record was
    # screened, including ones who later withdrew -- so it's simply the
    # total subject count, not gated on current status.
    counts = {stage: 0 for stage in STAGE_ORDER}
    counts["screened"] = len(subjects)
    withdrawn = 0
    for s in subjects:
        if s.status == "withdrawn":
            withdrawn += 1
            continue
        if s.status not in STAGE_ORDER:
            continue
        reached = STAGE_ORDER.index(s.status)
        # Stages beyond "screened" only count for subjects whose current
        # (non-withdrawn) status has actually reached them.
        for stage in STAGE_ORDER[1:reached + 1]:
            counts[stage] += 1

    study = db.query(models.Study).filter(models.Study.id == study_id).first()
    if not study:
        return
    study.screened_count = counts["screened"]
    study.eligible_count = counts["eligible"]
    study.enrolled_count = counts["enrolled"]
    study.randomized_count = counts["randomized"]
    study.completed_count = counts["completed"]
    study.withdrawn_count = withdrawn
