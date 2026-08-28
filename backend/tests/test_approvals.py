"""
Tests for approval safety: approve once succeeds, approving again doesn't
create a contradictory state, and rejecting after approval is blocked.
These exercise the actual approvals router logic against an in-memory DB.

Run with: pytest tests/test_approvals.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.main import app


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
    # Prevent the real startup seeding (which calls the Groq API) from
    # running against this isolated test DB.
    test_client = TestClient(app)
    yield test_client, TestSessionLocal
    app.dependency_overrides.clear()


def _make_pending_match(SessionLocal):
    db = SessionLocal()
    trial = models.Trial(name="T", condition="C", criteria="x", structured_criteria="[]")
    db.add(trial)
    db.commit()
    db.refresh(trial)
    patient = models.Patient(name="P", age=50, condition="C", biomarkers="")
    db.add(patient)
    db.commit()
    db.refresh(patient)
    match = models.PatientMatch(
        patient_id=patient.id, trial_id=trial.id, run_id="r1",
        fit_score=100.0, verdict="ELIGIBLE", rationale="test",
        outreach_draft="", criteria_results="[]", missing_info="[]",
        evidence="[]", status="pending_review",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    match_id = match.id
    db.close()
    return match_id


def test_approve_once_succeeds(client):
    test_client, SessionLocal = client
    match_id = _make_pending_match(SessionLocal)

    resp = test_client.post("/approvals/", json={
        "module": "patient_matching", "record_id": match_id, "action": "approved"
    })
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_approve_twice_does_not_duplicate_or_contradict(client):
    test_client, SessionLocal = client
    match_id = _make_pending_match(SessionLocal)

    r1 = test_client.post("/approvals/", json={
        "module": "patient_matching", "record_id": match_id, "action": "approved"
    })
    assert r1.json().get("ok") is True

    r2 = test_client.post("/approvals/", json={
        "module": "patient_matching", "record_id": match_id, "action": "approved"
    })
    # Same action twice should be a no-op, not an error and not a second log entry
    assert r2.json().get("ok") is True
    assert "already" in r2.json().get("note", "").lower()

    db = SessionLocal()
    logs = db.query(models.ApprovalLog).filter(models.ApprovalLog.record_id == match_id).all()
    assert len(logs) == 1, "Duplicate approval must not create a second audit log entry"
    db.close()


def test_reject_after_approval_is_blocked(client):
    test_client, SessionLocal = client
    match_id = _make_pending_match(SessionLocal)

    test_client.post("/approvals/", json={
        "module": "patient_matching", "record_id": match_id, "action": "approved"
    })
    r2 = test_client.post("/approvals/", json={
        "module": "patient_matching", "record_id": match_id, "action": "rejected"
    })
    assert "error" in r2.json()

    db = SessionLocal()
    match = db.query(models.PatientMatch).filter(models.PatientMatch.id == match_id).first()
    assert match.status == "approved", "Status must remain approved, not flip to rejected"
    db.close()


def test_approval_on_nonexistent_record_returns_error(client):
    test_client, _ = client
    resp = test_client.post("/approvals/", json={
        "module": "patient_matching", "record_id": 99999, "action": "approved"
    })
    assert "error" in resp.json()


def test_approval_on_unknown_module_returns_error(client):
    test_client, SessionLocal = client
    match_id = _make_pending_match(SessionLocal)
    resp = test_client.post("/approvals/", json={
        "module": "not_a_real_module", "record_id": match_id, "action": "approved"
    })
    assert "error" in resp.json()
