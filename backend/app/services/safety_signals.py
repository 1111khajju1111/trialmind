"""Priority 3(b) -- Safety Signal Engine.

Correlates AE/SAE cases (SafetyCase rows) that share a drug + batch number
and cluster in time, optionally concentrated at one site, and raises a
SafetySignal for human pharmacovigilance review.

IMPORTANT SCOPE NOTE (do not weaken this in the UI or in copy anywhere):
this module detects a *statistical correlation worth investigating* --
same drug, same batch, clustered in time, similar reported symptoms. It
does NOT detect, confirm, or claim a "contaminated batch." Contamination
is a laboratory finding. TrialMind's job ends at:

    AE/SAE -> drug/batch/site/time correlation -> signal -> human review

Any signal this engine raises is inert until a Pharmacovigilance officer
reviews it (open -> under_review) and a human decides whether to escalate
it for regulatory/investigation follow-up or dismiss it as noise. The
engine never auto-escalates and never auto-dismisses.

Clustering approach (deliberately simple / dependency-light, matching the
TF-IDF pattern already used for protocol evidence retrieval in
rag_service.py rather than reaching for a new dependency):

1. Group SafetyCases for the scope (one study, or across all studies) by
   (study_id, drug, batch_number) -- normalized, case-insensitive.
2. Within each group, sort by event_date and chain consecutive cases
   whose gap is <= window_hours into the same cluster (a rolling window,
   not a fixed bucket -- so a slow drip of related cases over a long
   afternoon still clusters together, the same way a real signal would
   present).
3. A cluster becomes a signal candidate only if it has at least
   min_patients distinct patients.
4. Symptom similarity is TF-IDF cosine similarity over event_term text,
   averaged pairwise across the cluster -- a demonstrator of "similar
   reported symptoms," not a MedDRA-grade coding step (see Priority 4 for
   the coding layer).
5. confidence_score blends three normalized signals: cluster size,
   symptom similarity, and site concentration. It is a triage aid for a
   human reviewer, not a statistical p-value.
"""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_WINDOW_HOURS = 6.0
DEFAULT_MIN_PATIENTS = 2  # demo-scale default; real deployments would tune this much higher

STATUS_ORDER = ["open", "under_review"]  # then a branch to escalated | dismissed
TERMINAL_STATUSES = {"escalated", "dismissed"}

SIGNAL_DISCLAIMER = (
    "This is a correlation signal (same drug, same batch, clustered in time, "
    "similar reported symptoms), surfaced for human pharmacovigilance review. "
    "It is not a confirmed finding of contamination, defect, or causality -- "
    "only laboratory testing and formal investigation can establish that. "
    "TrialMind does not auto-escalate or auto-dismiss signals."
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    return v or None


def _cluster_by_time(cases: list, window_hours: float) -> list[list]:
    """Chains cases sorted by event_date into clusters where each
    consecutive gap is <= window_hours. A rolling chain, not a fixed
    bucket, so a cluster's total span can exceed window_hours -- that's
    intentional (see module docstring)."""
    ordered = sorted(cases, key=lambda c: _aware(c.event_date))
    clusters: list[list] = []
    current: list = []
    for case in ordered:
        if not current:
            current = [case]
            continue
        gap = _aware(case.event_date) - _aware(current[-1].event_date)
        if gap <= timedelta(hours=window_hours):
            current.append(case)
        else:
            clusters.append(current)
            current = [case]
    if current:
        clusters.append(current)
    return clusters


def _symptom_similarity(cases: list) -> float:
    """Average pairwise TF-IDF cosine similarity of event_term text across
    the cluster. Returns 0.0 for a cluster of 1 (nothing to compare) or if
    vectorization fails on degenerate/empty text."""
    terms = [c.event_term or "" for c in cases]
    if len(terms) < 2 or not any(t.strip() for t in terms):
        return 0.0
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(terms)
        sims = cosine_similarity(matrix)
    except ValueError:
        return 0.0
    n = len(terms)
    total, count = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            total += sims[i][j]
            count += 1
    return round(total / count, 4) if count else 0.0


def _site_concentration(cases: list) -> tuple[float, int | None]:
    """Fraction of cases at the most common site, and that site's id (or
    None if cases don't concentrate at a single site, e.g. all site_id is
    None or the top site holds a minority)."""
    site_ids = [c.site_id for c in cases if c.site_id is not None]
    if not site_ids:
        return 0.0, None
    counts = Counter(site_ids)
    top_site, top_count = counts.most_common(1)[0]
    concentration = top_count / len(cases)
    return round(concentration, 4), (top_site if top_count > 1 else None)


def _location_concentration(cases: list) -> tuple[float, str | None]:
    """Priority 1 SIH improvement: fraction of cases at the most common
    free-text `location` (ward/clinic), and that location's label -- finer
    grained than site_concentration above, since a real cluster can sit
    inside one ward of a site rather than the whole site. Case-insensitive,
    trims whitespace; cases with no location recorded are excluded from
    both the numerator and denominator (missing data isn't evidence either
    way), mirroring how _site_concentration treats a missing site_id."""
    labels = [c.location.strip() for c in cases if c.location and c.location.strip()]
    if not labels:
        return 0.0, None
    counts = Counter(label.lower() for label in labels)
    top_key, top_count = counts.most_common(1)[0]
    concentration = top_count / len(cases)
    # Recover original casing for display from the first matching case.
    display_label = next(l for l in labels if l.lower() == top_key)
    return round(concentration, 4), (display_label if top_count > 1 else None)


def _confidence_score(patient_count: int, symptom_similarity: float, site_concentration: float) -> float:
    size_component = min(patient_count / 10.0, 1.0)  # saturates at 10 distinct patients
    score = 0.4 * size_component + 0.3 * symptom_similarity + 0.3 * site_concentration
    return round(min(max(score, 0.0), 1.0), 4)


def _severity_score(cases: list) -> float:
    if not cases:
        return 0.0
    fatal = sum(1 for c in cases if c.outcome == "fatal")
    serious = sum(1 for c in cases if c.is_serious)
    score = 0.6 * (fatal / len(cases)) + 0.4 * (serious / len(cases))
    return round(min(max(score, 0.0), 1.0), 4)


def _build_rationale(
    *, cases: list, patient_count: int, drug: str, batch_number: str,
    window_hours: float, site_name: str | None, site_concentration: float,
    symptom_similarity: float, top_terms: list[str],
    location_label: str | None = None, location_concentration: float = 0.0,
) -> str:
    span = _aware(cases[-1].event_date) - _aware(cases[0].event_date)
    span_hours = round(span.total_seconds() / 3600, 1)
    site_clause = (
        f" {round(site_concentration * 100)}% of these occurred at {site_name}."
        if site_name and site_concentration >= 0.6
        else ""
    )
    location_clause = (
        f" Within that, {round(location_concentration * 100)}% were reported at {location_label}."
        if location_label and location_concentration >= 0.6
        else ""
    )
    serious_count = sum(1 for c in cases if c.is_serious)
    serious_clause = f" {serious_count} of these case(s) are classified serious." if serious_count else ""
    terms_clause = f" Recurring terms: {', '.join(top_terms)}." if top_terms else ""

    return (
        f"{len(cases)} adverse event report(s) across {patient_count} distinct patient(s) "
        f"receiving drug '{drug}' (batch '{batch_number}') occurred within a {span_hours}-hour "
        f"span (clustering window {window_hours}h).{site_clause}{location_clause} Reported symptom terms show "
        f"{round(symptom_similarity * 100)}% average textual similarity.{terms_clause}"
        f"{serious_clause} Potential safety signal -- human investigation recommended. "
        + SIGNAL_DISCLAIMER
    )


def _top_terms(cases: list, k: int = 3) -> list[str]:
    words = Counter()
    for c in cases:
        for w in (c.event_term or "").lower().split():
            w = w.strip(".,;:")
            if len(w) > 3:
                words[w] += 1
    return [w for w, _ in words.most_common(k)]


def detect_signals(
    db, *, study_id: int | None = None, window_hours: float = DEFAULT_WINDOW_HOURS,
    min_patients: int = DEFAULT_MIN_PATIENTS,
) -> list:
    """Runs signal detection over SafetyCase rows in scope and creates or
    updates SafetySignal rows. Returns the list of SafetySignal ORM
    objects touched (created or refreshed) by this run.

    Only cases with both drug and batch_number populated are eligible --
    everything else is silently skipped (there's nothing to correlate on).
    Terminal signals (escalated/dismissed) are never modified by
    re-detection: that status is a frozen human decision.
    """
    from app import models  # local import: avoids a circular import with models.py

    query = db.query(models.SafetyCase).filter(
        models.SafetyCase.drug.isnot(None),
        models.SafetyCase.batch_number.isnot(None),
    )
    if study_id is not None:
        query = query.filter(models.SafetyCase.study_id == study_id)
    cases = [c for c in query.all() if _normalize(c.drug) and _normalize(c.batch_number)]

    groups: dict[tuple, list] = {}
    for c in cases:
        key = (c.study_id, _normalize(c.drug), _normalize(c.batch_number))
        groups.setdefault(key, []).append(c)

    touched = []
    for (grp_study_id, drug_norm, batch_norm), group_cases in groups.items():
        clusters = _cluster_by_time(group_cases, window_hours)
        for cluster in clusters:
            patient_ids = {c.patient_id for c in cluster}
            if len(patient_ids) < min_patients:
                continue

            symptom_similarity = _symptom_similarity(cluster)
            site_concentration, dominant_site_id = _site_concentration(cluster)
            location_concentration, dominant_location = _location_concentration(cluster)
            confidence = _confidence_score(len(patient_ids), symptom_similarity, site_concentration)
            severity = _severity_score(cluster)

            site_name = None
            if dominant_site_id is not None:
                site = db.query(models.Site).filter(models.Site.id == dominant_site_id).first()
                site_name = site.institution if site else None

            drug_display = cluster[0].drug
            batch_display = cluster[0].batch_number
            window_start = min(_aware(c.event_date) for c in cluster)
            window_end = max(_aware(c.event_date) for c in cluster)

            rationale = _build_rationale(
                cases=cluster, patient_count=len(patient_ids), drug=drug_display,
                batch_number=batch_display, window_hours=window_hours, site_name=site_name,
                site_concentration=site_concentration, symptom_similarity=symptom_similarity,
                top_terms=_top_terms(cluster),
                location_label=dominant_location, location_concentration=location_concentration,
            )

            signal_key = f"{grp_study_id}:{drug_norm}:{batch_norm}:{dominant_site_id or 'multi'}"

            existing = (
                db.query(models.SafetySignal)
                .filter(models.SafetySignal.signal_key == signal_key)
                .filter(models.SafetySignal.status.notin_(TERMINAL_STATUSES))
                .order_by(models.SafetySignal.id.desc())
                .first()
            )

            if existing:
                existing.site_id = dominant_site_id
                existing.window_start = window_start
                existing.window_end = window_end
                existing.case_ids = json.dumps(sorted(c.id for c in cluster))
                existing.patient_count = len(patient_ids)
                existing.case_count = len(cluster)
                existing.symptom_similarity = symptom_similarity
                existing.site_concentration = site_concentration
                existing.location_concentration = location_concentration
                existing.dominant_location = dominant_location
                existing.confidence_score = confidence
                existing.severity_score = severity
                existing.rationale = rationale
                db.add(existing)
                touched.append(existing)
            else:
                signal = models.SafetySignal(
                    study_id=grp_study_id,
                    site_id=dominant_site_id,
                    signal_key=signal_key,
                    drug=drug_display,
                    batch_number=batch_display,
                    window_start=window_start,
                    window_end=window_end,
                    case_ids=json.dumps(sorted(c.id for c in cluster)),
                    patient_count=len(patient_ids),
                    case_count=len(cluster),
                    symptom_similarity=symptom_similarity,
                    site_concentration=site_concentration,
                    location_concentration=location_concentration,
                    dominant_location=dominant_location,
                    confidence_score=confidence,
                    severity_score=severity,
                    rationale=rationale,
                    status="open",
                )
                db.add(signal)
                touched.append(signal)

    db.commit()
    for s in touched:
        db.refresh(s)
    return touched
