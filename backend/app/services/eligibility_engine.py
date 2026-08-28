"""
Deterministic eligibility engine.

Design principle: the LLM never judges pass/fail on objective criteria --
this module does that in plain Python, against structured rules extracted
from the protocol. The LLM's job (see agent_orchestrator.py) is to explain
the result and synthesize evidence, not to decide it.

Fix from the P0 review: a single numeric "fit score" can look like a medical
decision even when a required item is missing or an exclusion criterion
couldn't be verified. This engine instead produces one of four verdicts:

  ELIGIBLE             all inclusion criteria pass, no exclusion triggered,
                        nothing required is missing
  NOT_ELIGIBLE          a criterion deterministically failed (inclusion not
                        met, or exclusion criterion deterministically met)
  POTENTIAL_MATCH        no verified failure/exclusion, but one or more
                        verification-required or missing items remain --
                        this is a candidate for human review, not a match
  VERIFICATION_REQUIRED  used when missing data prevents any confident
                        verdict at all (distinct from POTENTIAL_MATCH,
                        which still has some passing signal)
"""
import json


def parse_biomarkers(biomarker_str: str) -> dict:
    """Turns 'HbA1c:7.8,BMI:29' into {'HbA1c': 7.8, 'BMI': 29}.
    Non-numeric values (e.g. 'RF:positive') are kept as strings."""
    result = {}
    if not biomarker_str:
        return result
    for pair in biomarker_str.split(","):
        if ":" not in pair:
            continue
        key, val = pair.split(":", 1)
        key, val = key.strip(), val.strip()
        try:
            result[key] = float(val)
        except ValueError:
            result[key] = val
    return result


def evaluate_criterion(criterion: dict, patient) -> dict:
    """Evaluates a single structured criterion against a patient.
    Returns a dict with label, crit_type (inclusion/exclusion),
    status (pass/fail/missing), detail, and source_text for traceability."""
    field = criterion.get("field", "")
    operator = criterion.get("operator", "")
    value = criterion.get("value")
    label = criterion.get("label", field)
    crit_type = criterion.get("type", "inclusion")
    unit = criterion.get("unit", "")
    source_text = criterion.get("source_text", "")
    verification_required = criterion.get("verification_required", False)

    base = {
        "criterion_id": criterion.get("criterion_id", label),
        "label": label,
        "crit_type": crit_type,
        "source_text": source_text,
    }

    # Criteria the extractor flagged as not confidently machine-checkable
    # are never evaluated here -- they're surfaced as needing human review
    # rather than having a rule invented for them.
    if verification_required or not operator:
        return {**base, "status": "missing",
                "detail": f"{label} requires manual verification (not machine-checkable)"}

    biomarkers = parse_biomarkers(patient.biomarkers)

    if field == "age":
        actual = patient.age
    elif field == "condition":
        actual = patient.condition
    elif field in biomarkers:
        actual = biomarkers[field]
    else:
        actual = None

    if actual is None:
        return {**base, "status": "missing",
                "detail": f"{label} not available in patient record"}

    unit_str = f" {unit}" if unit else ""
    try:
        if operator == "between" and isinstance(value, list) and len(value) == 2:
            ok = value[0] <= actual <= value[1]
            detail = f"{label}: {actual}{unit_str} (required {value[0]}-{value[1]}{unit_str})"
        elif operator == "gte":
            ok = actual >= value
            detail = f"{label}: {actual}{unit_str} (required >= {value}{unit_str})"
        elif operator == "lte":
            ok = actual <= value
            detail = f"{label}: {actual}{unit_str} (required <= {value}{unit_str})"
        elif operator == "equals":
            ok = str(actual).lower() == str(value).lower()
            detail = f"{label}: {actual} (required {value})"
        else:
            return {**base, "status": "missing", "detail": f"Unrecognized rule for {label}"}
    except TypeError:
        return {**base, "status": "missing",
                "detail": f"Could not compare {label} ({actual} vs {value})"}

    # For exclusion criteria, the *criterion* passing means the patient is
    # NOT excluded -- e.g. "eGFR >= 30" passing means the exclusion
    # (severe renal impairment) does not apply.
    return {**base, "status": "pass" if ok else "fail", "detail": detail}


def run_eligibility_check(structured_criteria_json: str, patient) -> dict:
    """Runs all structured criteria for a trial against one patient."""
    try:
        criteria = json.loads(structured_criteria_json) if structured_criteria_json else []
    except json.JSONDecodeError:
        criteria = []

    if not criteria:
        return {
            "verdict": "VERIFICATION_REQUIRED",
            "score": 0.0,
            "results": [],
            "missing_fields": [],
            "verified_count": 0,
            "total_count": 0,
        }

    results = [evaluate_criterion(c, patient) for c in criteria]

    inclusion_fails = [r for r in results if r["crit_type"] == "inclusion" and r["status"] == "fail"]
    exclusion_fails = [r for r in results if r["crit_type"] == "exclusion" and r["status"] == "fail"]
    missing = [r for r in results if r["status"] == "missing"]
    passes = [r for r in results if r["status"] == "pass"]

    # An exclusion criterion "failing" means the exclusion condition WAS met
    # (e.g. "eGFR >= 30" failed => patient has severe renal impairment => excluded)
    hard_fail = inclusion_fails or exclusion_fails

    if hard_fail:
        verdict = "NOT_ELIGIBLE"
    elif missing and not passes:
        verdict = "VERIFICATION_REQUIRED"
    elif missing:
        verdict = "POTENTIAL_MATCH"
    else:
        verdict = "ELIGIBLE"

    score = round(100 * len(passes) / len(results), 1) if results else 0.0

    return {
        "verdict": verdict,
        "score": score,
        "results": results,
        "missing_fields": [r["label"] for r in missing],
        "verified_count": len(passes),
        "total_count": len(results),
    }
