"""
Tests for the pharmacovigilance (Priority 3) hardening pass:
1. A safety case can only be recorded against a patient who is a
   StudySubject of that study.
2. Case status transitions are strictly sequential
   (Draft -> Under Review -> Reported -> Closed), no skipping, no going
   backward.
3. POST /safety/adverse-events and POST /safety/sae have strict,
   non-overlapping seriousness semantics.
4. The deadline engine computes due dates correctly and flags
   overdue/approaching/on_track appropriately.
5. GET /safety/dashboard aggregates AE/SAE counts correctly and always
   carries the deadline disclaimer.

Run with: pytest tests/test_safety.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone

import itertools

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.main import app
from app.services import safety as safety_svc

# POST /safety/cases/{id}/status is restricted to the "Pharmacovigilance"
# role (see app/rbac.py: require_role("Pharmacovigilance")). Tests that
# exercise the status-transition workflow need to send this header, or the
# RBAC middleware/dependency returns 403 before the transition logic under
# test ever runs.
PV_HEADERS = {"X-User-Role": "Pharmacovigilance"}


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client, TestSessionLocal
    app.dependency_overrides.clear()


_study_code_counter = itertools.count(1)


def _make_study_with_subject(SessionLocal, *, add_site=True, enroll_subject=True):
    """Creates a Study, optionally a Site, a Patient, and optionally a
    StudySubject linking the patient to the study. Returns
    (study_id, site_id_or_None, patient_id).

    Each call gets a unique study_code (studies.study_code is a unique
    column) so tests that create more than one study per test -- e.g. to
    prove a patient enrolled in one study can't have an AE recorded against
    a different study -- don't collide on the same fixture value.
    """
    db = SessionLocal()
    study = models.Study(
        study_code=f"STUDY-TEST-{next(_study_code_counter)}", title="Test Study", status="active"
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    site_id = None
    if add_site:
        site = models.Site(study_id=study.id, institution="Test Hospital")
        db.add(site)
        db.commit()
        db.refresh(site)
        site_id = site.id

    patient = models.Patient(name="Test Patient", age=50, condition="Test Condition")
    db.add(patient)
    db.commit()
    db.refresh(patient)

    if enroll_subject:
        subject = models.StudySubject(study_id=study.id, site_id=site_id, patient_id=patient.id, status="enrolled")
        db.add(subject)
        db.commit()

    study_id, patient_id = study.id, patient.id
    db.close()
    return study_id, site_id, patient_id


def _ae_payload(study_id, patient_id, site_id=None, **overrides):
    payload = {
        "study_id": study_id,
        "site_id": site_id,
        "patient_id": patient_id,
        "event_term": "Mild nausea",
        "severity": "mild",
        "seriousness": "not_serious",
        "outcome": "recovered",
        "causality": "possible",
    }
    payload.update(overrides)
    return payload


def _sae_payload(study_id, patient_id, site_id=None, **overrides):
    payload = {
        "study_id": study_id,
        "site_id": site_id,
        "patient_id": patient_id,
        "event_term": "Severe hypoglycemia requiring hospitalization",
        "severity": "severe",
        "seriousness": "hospitalization",
        "outcome": "recovered",
        "causality": "probable",
    }
    payload.update(overrides)
    return payload


# ---------- Fix #1: StudySubject validation ----------

def test_ae_rejected_when_patient_not_a_study_subject(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal, enroll_subject=False)

    resp = test_client.post("/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id))
    assert resp.status_code == 400
    assert "studysubject" in resp.json()["detail"].lower()


def test_ae_accepted_when_patient_is_a_study_subject(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)

    resp = test_client.post("/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id))
    assert resp.status_code == 200
    assert resp.json()["is_serious"] is False


def test_ae_rejected_when_patient_is_subject_of_a_different_study(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal, enroll_subject=False)
    other_study_id, _, other_patient_id = _make_study_with_subject(SessionLocal)

    # patient_id belongs to `study_id` but is only enrolled as a subject of
    # `other_study_id` -- must be rejected, not just "any subject anywhere".
    resp = test_client.post(
        "/safety/adverse-events", json=_ae_payload(study_id, other_patient_id, site_id)
    )
    assert resp.status_code == 400


def test_sae_rejected_when_patient_not_a_study_subject(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal, enroll_subject=False)

    resp = test_client.post("/safety/sae", json=_sae_payload(study_id, patient_id, site_id))
    assert resp.status_code == 400


def test_case_rejected_for_nonexistent_patient(client):
    test_client, SessionLocal = client
    study_id, site_id, _ = _make_study_with_subject(SessionLocal, enroll_subject=False)

    resp = test_client.post("/safety/adverse-events", json=_ae_payload(study_id, 99999, site_id))
    assert resp.status_code == 404


def test_case_rejected_for_nonexistent_study(client):
    test_client, _ = client
    resp = test_client.post("/safety/adverse-events", json=_ae_payload(99999, 1))
    assert resp.status_code == 404


# ---------- Fix #3: strict AE/SAE endpoint semantics ----------

def test_adverse_events_endpoint_rejects_serious_payload(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)

    resp = test_client.post(
        "/safety/adverse-events",
        json=_ae_payload(study_id, patient_id, site_id, seriousness="death"),
    )
    assert resp.status_code == 400
    assert "safety/sae" in resp.json()["detail"]


def test_sae_endpoint_rejects_not_serious_payload(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)

    resp = test_client.post(
        "/safety/sae",
        json=_sae_payload(study_id, patient_id, site_id, seriousness="not_serious"),
    )
    assert resp.status_code == 400
    assert "adverse-events" in resp.json()["detail"]


def test_sae_endpoint_accepts_each_serious_criterion(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)

    for criterion in ["death", "life_threatening", "hospitalization", "disability", "other_serious"]:
        resp = test_client.post(
            "/safety/sae",
            json=_sae_payload(study_id, patient_id, site_id, seriousness=criterion),
        )
        assert resp.status_code == 200, criterion
        assert resp.json()["is_serious"] is True
        assert resp.json()["seriousness"] == criterion


def test_adverse_events_list_only_returns_non_serious(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    test_client.post("/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id))
    test_client.post("/safety/sae", json=_sae_payload(study_id, patient_id, site_id))

    resp = test_client.get("/safety/adverse-events", params={"study_id": study_id})
    cases = resp.json()
    assert len(cases) == 1
    assert all(not c["is_serious"] for c in cases)


def test_sae_list_only_returns_serious(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    test_client.post("/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id))
    test_client.post("/safety/sae", json=_sae_payload(study_id, patient_id, site_id))

    resp = test_client.get("/safety/sae", params={"study_id": study_id})
    cases = resp.json()
    assert len(cases) == 1
    assert all(c["is_serious"] for c in cases)


# ---------- Fix #2: strictly sequential status transitions ----------

def test_status_advances_one_step_at_a_time(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    case_id = test_client.post(
        "/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id)
    ).json()["id"]

    assert test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "under_review"}, headers=PV_HEADERS).status_code == 200
    assert test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "reported"}, headers=PV_HEADERS).status_code == 200
    assert test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "closed"}, headers=PV_HEADERS).status_code == 200

    final = test_client.get(f"/safety/cases/{case_id}").json()
    assert final["status"] == "closed"
    assert final["reported_date"] is not None


def test_status_cannot_skip_ahead(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    case_id = test_client.post(
        "/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id)
    ).json()["id"]

    # draft -> reported skips "under_review"
    resp = test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "reported"}, headers=PV_HEADERS)
    assert resp.status_code == 400
    assert "skip" in resp.json()["detail"].lower()

    unchanged = test_client.get(f"/safety/cases/{case_id}").json()
    assert unchanged["status"] == "draft"


def test_status_cannot_go_backward(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    case_id = test_client.post(
        "/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id)
    ).json()["id"]
    test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "under_review"}, headers=PV_HEADERS)
    test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "reported"}, headers=PV_HEADERS)

    resp = test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "draft"}, headers=PV_HEADERS)
    assert resp.status_code == 400
    assert "backward" in resp.json()["detail"].lower()

    unchanged = test_client.get(f"/safety/cases/{case_id}").json()
    assert unchanged["status"] == "reported"


def test_status_resubmit_same_value_is_a_noop(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    case_id = test_client.post(
        "/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id)
    ).json()["id"]

    resp = test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "draft"}, headers=PV_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


def test_status_update_on_nonexistent_case_returns_404(client):
    test_client, _ = client
    resp = test_client.patch("/safety/cases/99999/status", json={"status": "under_review"}, headers=PV_HEADERS)
    assert resp.status_code == 404


# ---------- Deadline engine ----------

def test_deadline_engine_fatal_and_life_threatening_are_24_hours():
    event_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for criterion in ["death", "life_threatening"]:
        due = safety_svc.compute_due_date(event_date, criterion)
        assert due - event_date == timedelta(hours=24), criterion


def test_deadline_engine_other_serious_criteria_are_7_days():
    event_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for criterion in ["hospitalization", "disability", "other_serious"]:
        due = safety_svc.compute_due_date(event_date, criterion)
        assert due - event_date == timedelta(days=7), criterion


def test_deadline_engine_non_serious_is_15_days():
    event_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = safety_svc.compute_due_date(event_date, "not_serious")
    assert due - event_date == timedelta(days=15)


def test_due_status_overdue_approaching_on_track():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    overdue_due = now - timedelta(hours=1)
    approaching_due = now + timedelta(hours=10)
    on_track_due = now + timedelta(days=5)

    assert safety_svc.due_status(overdue_due, "draft", now=now) == "overdue"
    assert safety_svc.due_status(approaching_due, "under_review", now=now) == "approaching"
    assert safety_svc.due_status(on_track_due, "draft", now=now) == "on_track"


def test_due_status_is_none_once_reported_or_closed():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    overdue_due = now - timedelta(days=10)
    assert safety_svc.due_status(overdue_due, "reported", now=now) is None
    assert safety_svc.due_status(overdue_due, "closed", now=now) is None


def test_case_created_with_serious_criterion_gets_correct_due_status(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    # Event happened 1 hour ago; life_threatening -> due 24h after event,
    # i.e. ~23h from now -- inside the 48h "approaching" window but not
    # overdue yet.
    event_date = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    resp = test_client.post(
        "/safety/sae",
        json=_sae_payload(study_id, patient_id, site_id, seriousness="life_threatening", event_date=event_date),
    )
    data = resp.json()
    assert data["due_status"] == "approaching"

    # An event from 2 days ago against the same 24h SAE window is overdue.
    old_event_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    resp2 = test_client.post(
        "/safety/sae",
        json=_sae_payload(study_id, patient_id, site_id, seriousness="life_threatening", event_date=old_event_date),
    )
    assert resp2.json()["due_status"] == "overdue"


# ---------- Safety dashboard ----------

def test_dashboard_counts_ae_and_sae_separately(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    test_client.post("/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id))
    test_client.post("/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id))
    test_client.post("/safety/sae", json=_sae_payload(study_id, patient_id, site_id))

    resp = test_client.get("/safety/dashboard", params={"study_id": study_id})
    data = resp.json()
    assert data["ae_count"] == 2
    assert data["sae_count"] == 1
    assert data["total_cases"] == 3
    assert data["open_cases"] == 3  # all still "draft"


def test_dashboard_open_cases_excludes_reported_and_closed(client):
    test_client, SessionLocal = client
    study_id, site_id, patient_id = _make_study_with_subject(SessionLocal)
    case_id = test_client.post(
        "/safety/adverse-events", json=_ae_payload(study_id, patient_id, site_id)
    ).json()["id"]
    test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "under_review"}, headers=PV_HEADERS)
    test_client.patch(f"/safety/cases/{case_id}/status", json={"status": "reported"}, headers=PV_HEADERS)

    resp = test_client.get("/safety/dashboard", params={"study_id": study_id})
    assert resp.json()["open_cases"] == 0


# ---------- Fix #5: deadline disclaimer ----------

def test_dashboard_always_carries_deadline_disclaimer(client):
    test_client, _ = client
    resp = test_client.get("/safety/dashboard")
    assert resp.status_code == 200
    disclaimer = resp.json().get("deadline_disclaimer", "")
    assert "not" in disclaimer.lower() and "validated" in disclaimer.lower()
