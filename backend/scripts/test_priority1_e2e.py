"""
Priority 1 end-to-end smoke test: creation -> site -> patient -> recruitment.

Exercises the exact flow from Section 16 of the implementation plan against
a LIVE backend (not the seeded demo data) so you can confirm the whole
Study -> Site -> StudySubject -> derived-recruitment chain actually works,
not just that it seeds correctly.

Usage:
    1. Start the backend:  uvicorn app.main:app --reload  (from backend/)
    2. In another terminal, from backend/:
           pip install requests   # if not already available
           python scripts/test_priority1_e2e.py

This calls POST /admin/reset first, which wipes all data back to the seeded
demo state (only runs while settings.demo_mode is true, which is the
default). Safe on a dev/demo database; do not point this at anything with
real data.
"""
import sys
import requests

BASE = "http://localhost:8000"


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


FAILURES = []


def main():
    try:
        requests.get(f"{BASE}/health", timeout=3)
    except requests.exceptions.ConnectionError:
        print(f"Could not reach {BASE}. Is the backend running (uvicorn app.main:app)?")
        sys.exit(1)

    print("== Resetting to known demo state ==")
    r = requests.post(f"{BASE}/admin/reset")
    check("admin reset succeeds", r.status_code == 200, r.text)

    print("\n== 1. Create a new synthetic study ==")
    r = requests.post(f"{BASE}/studies/", json={
        "study_code": "E2E-TEST-01",
        "title": "Synthetic Ayurveda Trial for SIH Demo",
        "phase": "Phase II",
        "intervention": "Investigational herbal formulation",
        "principal_investigator": "Dr. Test PI",
        "target_enrollment": 20,
        "status": "active",
    })
    check("create study returns 200", r.status_code == 200, r.text)
    study = r.json()
    study_id = study.get("id")
    check("new study starts at 0 recruitment", study.get("screened_count") == 0)

    print("\n== 2. Add two sites ==")
    r1 = requests.post(f"{BASE}/studies/{study_id}/sites", json={
        "institution": "Test Site Alpha", "site_code": "E2E-SITE-A",
        "pi_name": "Dr. Alpha", "enrollment_target": 10, "activation_status": "activated",
    })
    r2 = requests.post(f"{BASE}/studies/{study_id}/sites", json={
        "institution": "Test Site Beta", "site_code": "E2E-SITE-B",
        "pi_name": "Dr. Beta", "enrollment_target": 10, "activation_status": "pending",
    })
    check("site A created", r1.status_code == 200, r1.text)
    check("site B created", r2.status_code == 200, r2.text)
    site_a_id = r1.json().get("id")

    r = requests.get(f"{BASE}/studies/{study_id}/sites")
    check("study has 2 sites", len(r.json()) == 2)

    print("\n== 3. Add a milestone (IEC approval, overdue on purpose) ==")
    r = requests.post(f"{BASE}/studies/{study_id}/milestones", json={
        "milestone_type": "iec_approval",
        "name": "IEC Approval",
        "planned_date": "2020-01-01T00:00:00Z",  # deliberately in the past, no actual_date
    })
    check("milestone created", r.status_code == 200, r.text)

    r = requests.get(f"{BASE}/studies/{study_id}/milestones")
    overdue = [m for m in r.json() if m["status"] == "overdue"]
    check("overdue milestone auto-flagged on read", len(overdue) == 1, r.text)

    print("\n== 4. Pull a real patient and run them through the recruitment funnel ==")
    r = requests.get(f"{BASE}/patients/")
    check("patients endpoint returns data", r.status_code == 200 and len(r.json()) > 0)
    patient = r.json()[0]
    patient_id = patient["id"]

    r = requests.post(f"{BASE}/studies/{study_id}/subjects", json={
        "patient_id": patient_id, "site_id": site_a_id, "status": "screened",
        "notes": "E2E test subject",
    })
    check("subject created (screened)", r.status_code == 200, r.text)
    subject_id = r.json().get("id")
    check("subject links to correct patient", r.json().get("patient_id") == patient_id)
    check("subject links to correct site", r.json().get("site_id") == site_a_id)

    r = requests.get(f"{BASE}/studies/{study_id}")
    d = r.json()
    check("recruitment: screened=1 after adding subject", d["study"]["screened_count"] == 1, d)
    check("recruitment: eligible=0 before advancing", d["study"]["eligible_count"] == 0)

    for target_status in ["eligible", "enrolled", "randomized", "completed"]:
        r = requests.patch(f"{BASE}/studies/{study_id}/subjects/{subject_id}", json={"status": target_status})
        check(f"subject advanced to {target_status}", r.status_code == 200 and r.json()["status"] == target_status, r.text)

    r = requests.get(f"{BASE}/studies/{study_id}")
    d = r.json()["study"]
    check("recruitment funnel fully derived: screened=1", d["screened_count"] == 1, d)
    check("recruitment funnel fully derived: eligible=1", d["eligible_count"] == 1, d)
    check("recruitment funnel fully derived: enrolled=1", d["enrolled_count"] == 1, d)
    check("recruitment funnel fully derived: randomized=1", d["randomized_count"] == 1, d)
    check("recruitment funnel fully derived: completed=1", d["completed_count"] == 1, d)

    print("\n== 5. Add a protocol deviation and a monitoring visit ==")
    r = requests.post(f"{BASE}/studies/{study_id}/deviations", json={
        "site_id": site_a_id, "description": "E2E test deviation.", "severity": "minor",
    })
    check("deviation recorded", r.status_code == 200, r.text)

    r = requests.post(f"{BASE}/studies/{study_id}/monitoring-visits", json={
        "site_id": site_a_id, "findings": "E2E test visit, no issues.",
    })
    check("monitoring visit recorded", r.status_code == 200, r.text)

    r = requests.get(f"{BASE}/studies/{study_id}")
    check("open_deviation_count reflects the new deviation", r.json()["open_deviation_count"] == 1)

    print("\n== 6. Portfolio dashboard reflects the new study ==")
    r = requests.get(f"{BASE}/dashboard/portfolio")
    check("portfolio endpoint returns 200", r.status_code == 200, r.text)
    portfolio = r.json()
    ids = [s["id"] for s in portfolio["studies"]]
    check("new study appears in portfolio", study_id in ids)
    check("portfolio total_enrolled includes the completed subject", portfolio["total_enrolled"] >= 1)

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED -- Priority 1 core CTMS flow verified end-to-end.")


if __name__ == "__main__":
    main()
