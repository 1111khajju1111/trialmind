"""
Tests for the Priority 3(b) Safety Signal Engine:
1. A cluster of AE cases sharing drug+batch within the time window, across
   enough distinct patients, raises a signal.
2. Cases below the min_patients threshold, or with different drug/batch,
   or outside the time window, do NOT raise a signal.
3. Cases missing drug or batch_number are excluded from detection.
4. Re-running detection updates an open/under_review signal in place
   (dedup via signal_key) rather than creating a duplicate.
5. The human-review status workflow is enforced: open -> under_review is
   required first; under_review branches to escalated | dismissed; both
   are terminal (re-detection and further status changes cannot touch it).
6. GET /safety/signals/{id} returns the underlying cases.

Run with: pytest tests/test_safety_signals.py -v
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


def _make_study(SessionLocal, *, add_site=True):
    db = SessionLocal()
    study = models.Study(
        study_code=f"STUDY-SIG-{next(_study_code_counter)}", title="Signal Test Study", status="active"
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    site_id = None
    if add_site:
        site = models.Site(study_id=study.id, institution="Signal Test Hospital")
        db.add(site)
        db.commit()
        db.refresh(site)
        site_id = site.id

    study_id = study.id
    db.close()
    return study_id, site_id


def _make_subject(SessionLocal, study_id, site_id, name="Patient"):
    db = SessionLocal()
    patient = models.Patient(name=name, age=45, condition="Test Condition")
    db.add(patient)
    db.commit()
    db.refresh(patient)
    subject = models.StudySubject(study_id=study_id, site_id=site_id, patient_id=patient.id, status="enrolled")
    db.add(subject)
    db.commit()
    patient_id = patient.id
    db.close()
    return patient_id


def _ae_payload(study_id, patient_id, site_id, *, drug, batch, event_term, event_date, **overrides):
    payload = {
        "study_id": study_id,
        "site_id": site_id,
        "patient_id": patient_id,
        "event_term": event_term,
        "event_date": event_date.isoformat(),
        "severity": "moderate",
        "seriousness": "not_serious",
        "outcome": "recovering",
        "causality": "possible",
        "drug": drug,
        "batch_number": batch,
    }
    payload.update(overrides)
    return payload


def _post_ae(test_client, payload):
    resp = test_client.post("/safety/adverse-events", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------- Cluster detection ----------

def test_cluster_of_cases_raises_signal(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea and dizziness", event_date=now + timedelta(minutes=20 * i),
        ))

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["signals_detected"] == 1
    signal = body["signals"][0]
    assert signal["drug"] == "Metformin"
    assert signal["batch_number"] == "BATCH-001"
    assert signal["patient_count"] == 3
    assert signal["case_count"] == 3
    assert signal["status"] == "open"
    assert 0.0 < signal["confidence_score"] <= 1.0
    assert "human investigation" in signal["rationale"].lower()


def test_below_min_patients_does_not_raise_signal(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    for i in range(2):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(minutes=10 * i),
        ))

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["signals_detected"] == 0


def test_different_batches_do_not_cluster_together(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        batch = "BATCH-001" if i < 2 else "BATCH-002"
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch=batch,
            event_term="nausea", event_date=now + timedelta(minutes=10 * i),
        ))

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["signals_detected"] == 0  # 2 in one batch, 1 in another -- neither hits threshold


def test_events_outside_window_do_not_cluster(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        # 10 hours apart each -- outside a 1-hour window, so no chain forms
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(hours=10 * i),
        ))

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 1, "min_patients": 3},
        headers=PV_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["signals_detected"] == 0


def test_cases_missing_drug_or_batch_are_excluded(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        payload = _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(minutes=5 * i),
        )
        if i == 2:
            payload["drug"] = None  # missing drug -- must be excluded from clustering
        _post_ae(test_client, payload)

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    assert resp.status_code == 200
    # only 2 eligible cases remain -- below the min_patients=3 threshold
    assert resp.json()["signals_detected"] == 0


# ---------- Re-detection dedup ----------

def test_redetection_updates_open_signal_in_place(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    patient_ids = []
    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        patient_ids.append(pid)
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(minutes=10 * i),
        ))

    resp1 = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal_id = resp1.json()["signals"][0]["id"]

    # a 4th case joins the same cluster
    pid4 = _make_subject(SessionLocal, study_id, site_id, name="Patient 4")
    _post_ae(test_client, _ae_payload(
        study_id, pid4, site_id, drug="Metformin", batch="BATCH-001",
        event_term="nausea", event_date=now + timedelta(minutes=40),
    ))

    resp2 = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    assert resp2.json()["signals_detected"] == 1
    updated = resp2.json()["signals"][0]
    assert updated["id"] == signal_id  # same signal, updated -- not a duplicate
    assert updated["patient_count"] == 4

    listing = test_client.get(f"/safety/signals?study_id={study_id}").json()
    assert len(listing) == 1


def test_terminal_signal_is_not_modified_by_redetection(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(minutes=10 * i),
        ))

    resp1 = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal_id = resp1.json()["signals"][0]["id"]

    test_client.patch(f"/safety/signals/{signal_id}/status", json={"status": "under_review"}, headers=PV_HEADERS)
    test_client.patch(
        f"/safety/signals/{signal_id}/status",
        json={"status": "dismissed", "review_notes": "Known GI side effect, not batch-related."},
        headers=PV_HEADERS,
    )

    # a new case joins what would be the same cluster
    pid4 = _make_subject(SessionLocal, study_id, site_id, name="Patient 4")
    _post_ae(test_client, _ae_payload(
        study_id, pid4, site_id, drug="Metformin", batch="BATCH-001",
        event_term="nausea", event_date=now + timedelta(minutes=40),
    ))

    resp2 = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    # dismissed signal untouched; a fresh distinct cluster (same key) is
    # opened instead since the old one is terminal
    dismissed = test_client.get(f"/safety/signals/{signal_id}").json()
    assert dismissed["status"] == "dismissed"
    assert dismissed["patient_count"] == 3  # unchanged

    all_signals = test_client.get(f"/safety/signals?study_id={study_id}").json()
    assert any(s["status"] == "open" for s in all_signals)


# ---------- Human review status workflow ----------

def test_signal_status_must_go_through_under_review_first(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)
    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(minutes=10 * i),
        ))
    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal_id = resp.json()["signals"][0]["id"]

    bad = test_client.patch(f"/safety/signals/{signal_id}/status", json={"status": "escalated"}, headers=PV_HEADERS)
    assert bad.status_code == 400

    ok = test_client.patch(f"/safety/signals/{signal_id}/status", json={"status": "under_review"}, headers=PV_HEADERS)
    assert ok.status_code == 200
    assert ok.json()["status"] == "under_review"
    assert ok.json()["reviewed_by"] is not None


def test_signal_status_requires_pharmacovigilance_role(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)
    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea", event_date=now + timedelta(minutes=10 * i),
        ))
    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal_id = resp.json()["signals"][0]["id"]

    denied = test_client.patch(
        f"/safety/signals/{signal_id}/status", json={"status": "under_review"},
        headers={"X-User-Role": "Study Coordinator"},
    )
    assert denied.status_code == 403


def test_get_signal_returns_underlying_cases(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)
    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="nausea and dizziness", event_date=now + timedelta(minutes=10 * i),
        ))
    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal_id = resp.json()["signals"][0]["id"]

    detail = test_client.get(f"/safety/signals/{signal_id}").json()
    assert len(detail["cases"]) == 3
    assert all(c["drug"] == "Metformin" for c in detail["cases"])


# ---------- Priority 1 SIH improvement: location concentration ----------

def test_signal_reports_location_concentration_within_a_site(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    # All three cases share the same site AND the same free-text ward --
    # location_concentration should be 100%, finer-grained than the
    # site-level concentration.
    for i in range(3):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="rash and swelling", event_date=now + timedelta(minutes=15 * i),
            location="Ward B",
        ))

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal = resp.json()["signals"][0]
    assert signal["dominant_location"] == "Ward B"
    assert signal["location_concentration"] == pytest.approx(1.0)


def test_signal_omits_dominant_location_when_locations_differ(client):
    test_client, SessionLocal = client
    study_id, site_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    locations = ["Ward A", "Ward B", "Ward C"]
    for i, loc in enumerate(locations):
        pid = _make_subject(SessionLocal, study_id, site_id, name=f"Patient {i}")
        _post_ae(test_client, _ae_payload(
            study_id, pid, site_id, drug="Metformin", batch="BATCH-001",
            event_term="rash and swelling", event_date=now + timedelta(minutes=15 * i),
            location=loc,
        ))

    resp = test_client.post(
        "/safety/signals/detect", json={"study_id": study_id, "window_hours": 6, "min_patients": 3},
        headers=PV_HEADERS,
    )
    signal = resp.json()["signals"][0]
    # No single location holds more than one case, so there's no dominant
    # location -- a lone top count of 1 shouldn't be reported as "the"
    # concentrated location.
    assert signal["dominant_location"] is None
