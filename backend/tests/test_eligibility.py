"""
Unit tests for the deterministic eligibility engine.

These need no database, no API key, and no network -- they exercise
app/services/eligibility_engine.py directly. This is intentional: the
review flags the eligibility engine as the single most safety-critical
piece of TrialMind, so it gets the most thorough, fastest, most reliable
test coverage. Run with: pytest tests/test_eligibility.py -v
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.eligibility_engine import run_eligibility_check, parse_biomarkers


class FakePatient:
    """Standalone stand-in for the SQLAlchemy Patient model so these tests
    don't need a database."""
    def __init__(self, age, condition, biomarkers):
        self.age = age
        self.condition = condition
        self.biomarkers = biomarkers


GLYCO3_CRITERIA = json.dumps([
    {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
     "operator": "between", "value": [40, 65], "unit": "years",
     "source_text": "40-65 yrs", "verification_required": False},
    {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
     "operator": "equals", "value": "Type 2 Diabetes", "unit": "",
     "source_text": "T2D diagnosis", "verification_required": False},
    {"criterion_id": "hba1c_range", "type": "inclusion", "field": "HbA1c", "label": "HbA1c",
     "operator": "between", "value": [7.0, 9.5], "unit": "%",
     "source_text": "HbA1c 7.0-9.5%", "verification_required": False},
    {"criterion_id": "bmi_range", "type": "inclusion", "field": "BMI", "label": "BMI",
     "operator": "between", "value": [27, 35], "unit": "kg/m^2",
     "source_text": "BMI 27-35", "verification_required": False},
    {"criterion_id": "no_prior_insulin", "type": "inclusion", "field": "prior_insulin_use",
     "label": "No prior insulin therapy", "operator": None, "value": None, "unit": "",
     "source_text": "No prior insulin", "verification_required": True},
    {"criterion_id": "renal_function", "type": "exclusion", "field": "eGFR",
     "label": "Renal function (eGFR)", "operator": "gte", "value": 30, "unit": "mL/min/1.73m^2",
     "source_text": "eGFR < 30 excluded", "verification_required": False},
    {"criterion_id": "cv_event", "type": "exclusion", "field": "recent_cv_event",
     "label": "No recent cardiovascular event", "operator": None, "value": None, "unit": "",
     "source_text": "No CV event in 6mo", "verification_required": True},
])

# All-machine-checkable criteria set (LIPID-2 style), used for tests that
# need a clean ELIGIBLE to be actually reachable.
CLEAN_CRITERIA = json.dumps([
    {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
     "operator": "between", "value": [35, 70], "unit": "years",
     "source_text": "35-70", "verification_required": False},
    {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
     "operator": "equals", "value": "Hyperlipidemia", "unit": "",
     "source_text": "dx", "verification_required": False},
    {"criterion_id": "ldl_range", "type": "inclusion", "field": "LDL", "label": "LDL",
     "operator": "between", "value": [130, 190], "unit": "mg/dL",
     "source_text": "LDL", "verification_required": False},
    {"criterion_id": "renal_function", "type": "exclusion", "field": "eGFR",
     "label": "eGFR", "operator": "gte", "value": 45, "unit": "",
     "source_text": "eGFR", "verification_required": False},
])


# ---------- parse_biomarkers ----------

def test_parse_biomarkers_numeric():
    assert parse_biomarkers("HbA1c:7.8,BMI:29") == {"HbA1c": 7.8, "BMI": 29.0}


def test_parse_biomarkers_mixed_types():
    result = parse_biomarkers("HbA1c:7.8,RF:positive")
    assert result["HbA1c"] == 7.8
    assert result["RF"] == "positive"


def test_parse_biomarkers_empty():
    assert parse_biomarkers("") == {}
    assert parse_biomarkers(None) == {}


# ---------- age PASS / FAIL ----------

def test_age_pass():
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8,BMI:29,eGFR:75")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    age_result = next(c for c in r["results"] if c["criterion_id"] == "age_range")
    assert age_result["status"] == "pass"


def test_age_fail_too_old():
    p = FakePatient(71, "Type 2 Diabetes", "HbA1c:7.5,BMI:28,eGFR:60")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    age_result = next(c for c in r["results"] if c["criterion_id"] == "age_range")
    assert age_result["status"] == "fail"
    assert r["verdict"] == "NOT_ELIGIBLE"


# ---------- HbA1c PASS / FAIL ----------

def test_hba1c_pass():
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8,BMI:29,eGFR:75")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    hba1c_result = next(c for c in r["results"] if c["criterion_id"] == "hba1c_range")
    assert hba1c_result["status"] == "pass"


def test_hba1c_fail_too_high():
    p = FakePatient(61, "Type 2 Diabetes", "HbA1c:10.2,BMI:31,eGFR:60")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    hba1c_result = next(c for c in r["results"] if c["criterion_id"] == "hba1c_range")
    assert hba1c_result["status"] == "fail"
    assert r["verdict"] == "NOT_ELIGIBLE"


# ---------- BMI PASS / FAIL ----------

def test_bmi_pass():
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8,BMI:29,eGFR:75")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    bmi_result = next(c for c in r["results"] if c["criterion_id"] == "bmi_range")
    assert bmi_result["status"] == "pass"


def test_bmi_fail_too_high():
    p = FakePatient(50, "Type 2 Diabetes", "HbA1c:8.0,BMI:40,eGFR:60")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    bmi_result = next(c for c in r["results"] if c["criterion_id"] == "bmi_range")
    assert bmi_result["status"] == "fail"
    assert r["verdict"] == "NOT_ELIGIBLE"


# ---------- missing eGFR -> verification/potential match ----------

def test_missing_egfr_is_not_a_silent_pass():
    p = FakePatient(58, "Type 2 Diabetes", "HbA1c:8.4,BMI:33")  # no eGFR provided
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    renal_result = next(c for c in r["results"] if c["criterion_id"] == "renal_function")
    assert renal_result["status"] == "missing", "Missing data must never be silently treated as a pass"
    assert r["verdict"] in ("POTENTIAL_MATCH", "VERIFICATION_REQUIRED")
    assert r["verdict"] != "ELIGIBLE"


# ---------- exclusion criteria ----------

def test_exclusion_criterion_triggers_not_eligible():
    # eGFR 20 < 30 threshold -> renal impairment present -> excluded
    p = FakePatient(50, "Type 2 Diabetes", "HbA1c:8.0,BMI:30,eGFR:20")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    renal_result = next(c for c in r["results"] if c["criterion_id"] == "renal_function")
    assert renal_result["status"] == "fail"
    assert renal_result["crit_type"] == "exclusion"
    assert r["verdict"] == "NOT_ELIGIBLE"


def test_exclusion_criterion_passing_means_not_excluded():
    p = FakePatient(50, "Type 2 Diabetes", "HbA1c:8.0,BMI:30,eGFR:75")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    renal_result = next(c for c in r["results"] if c["criterion_id"] == "renal_function")
    assert renal_result["status"] == "pass"  # eGFR 75 >= 30, exclusion does NOT apply


# ---------- verification_required criteria ----------

def test_verification_required_criterion_is_always_missing_never_invented():
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8,BMI:29,eGFR:75")
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    insulin_result = next(c for c in r["results"] if c["criterion_id"] == "no_prior_insulin")
    assert insulin_result["status"] == "missing"
    assert "manual verification" in insulin_result["detail"]


# ---------- all four verdict types ----------

def test_verdict_eligible_when_all_machine_checkable_criteria_pass():
    p = FakePatient(52, "Hyperlipidemia", "LDL:165,eGFR:88")
    r = run_eligibility_check(CLEAN_CRITERIA, p)
    assert r["verdict"] == "ELIGIBLE"


def test_verdict_not_eligible_on_hard_failure():
    p = FakePatient(20, "Hyperlipidemia", "LDL:165,eGFR:88")  # age below range
    r = run_eligibility_check(CLEAN_CRITERIA, p)
    assert r["verdict"] == "NOT_ELIGIBLE"


def test_verdict_potential_match_when_some_missing_but_some_pass():
    p = FakePatient(58, "Type 2 Diabetes", "HbA1c:8.4,BMI:33")  # missing eGFR, but age/hba1c/bmi pass
    r = run_eligibility_check(GLYCO3_CRITERIA, p)
    assert r["verdict"] == "POTENTIAL_MATCH"


def test_verdict_verification_required_when_nothing_can_be_confirmed():
    # A criteria set where every single criterion is verification-required
    # (or the only checkable one fails) should never present as a confident
    # match of any kind.
    all_verification_criteria = json.dumps([
        {"criterion_id": "vague_1", "type": "inclusion", "field": "unknown_field",
         "label": "Adequate organ function", "operator": None, "value": None, "unit": "",
         "source_text": "vague", "verification_required": True},
    ])
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8")
    r = run_eligibility_check(all_verification_criteria, p)
    assert r["verdict"] == "VERIFICATION_REQUIRED"


def test_empty_criteria_list_is_verification_required_not_eligible():
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8")
    r = run_eligibility_check("[]", p)
    assert r["verdict"] == "VERIFICATION_REQUIRED"
    assert r["total_count"] == 0


def test_malformed_criteria_json_does_not_crash():
    p = FakePatient(54, "Type 2 Diabetes", "HbA1c:7.8")
    r = run_eligibility_check("not valid json{{{", p)
    assert r["verdict"] == "VERIFICATION_REQUIRED"
