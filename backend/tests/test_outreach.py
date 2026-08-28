"""
Tests for the outreach generation gate: must be blocked before approval,
allowed after, and idempotent (doesn't regenerate/re-call the LLM if a draft
already exists). Mocks ask_llm so this runs with no API key/network.

Run with: pytest tests/test_outreach.py -v
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
import app.routers.patients as patients_module


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


def _make_match(SessionLocal, status="pending_review"):
    db = SessionLocal()
    trial = models.Trial(name="T", condition="C", criteria="x", structured_criteria="[]")
    db.add(trial)
    db.commit(); db.refresh(trial)
    patient = models.Patient(name="P", age=50, condition="C", biomarkers="")
    db.add(patient)
    db.commit(); db.refresh(patient)
    match = models.PatientMatch(
        patient_id=patient.id, trial_id=trial.id, run_id="r1",
        fit_score=100.0, verdict="ELIGIBLE", rationale="test rationale",
        outreach_draft="", criteria_results="[]", missing_info="[]",
        evidence="[]", status=status,
    )
    db.add(match)
    db.commit(); db.refresh(match)
    match_id = match.id
    db.close()
    return match_id


def test_outreach_blocked_before_approval(client):
    test_client, SessionLocal = client
    match_id = _make_match(SessionLocal, status="pending_review")

    resp = test_client.post(f"/patients/matches/{match_id}/outreach")
    assert "error" in resp.json()

    db = SessionLocal()
    match = db.query(models.PatientMatch).filter(models.PatientMatch.id == match_id).first()
    assert match.outreach_draft == ""
    db.close()


def test_outreach_allowed_after_approval(client, monkeypatch):
    test_client, SessionLocal = client
    match_id = _make_match(SessionLocal, status="approved")

    monkeypatch.setattr(patients_module, "ask_llm", lambda *a, **k: "Dear Dr. Smith, ...")

    resp = test_client.post(f"/patients/matches/{match_id}/outreach")
    body = resp.json()
    assert "error" not in body
    assert body["outreach_draft"] == "Dear Dr. Smith, ..."


def test_outreach_is_idempotent_does_not_regenerate(client, monkeypatch):
    test_client, SessionLocal = client
    match_id = _make_match(SessionLocal, status="approved")

    call_count = {"n": 0}
    def counting_ask_llm(*a, **k):
        call_count["n"] += 1
        return f"Draft version {call_count['n']}"

    monkeypatch.setattr(patients_module, "ask_llm", counting_ask_llm)

    r1 = test_client.post(f"/patients/matches/{match_id}/outreach")
    r2 = test_client.post(f"/patients/matches/{match_id}/outreach")

    assert r1.json()["outreach_draft"] == r2.json()["outreach_draft"]
    assert call_count["n"] == 1, "ask_llm should only be called once; second call should reuse the existing draft"


def test_outreach_on_rejected_match_is_blocked(client):
    test_client, SessionLocal = client
    match_id = _make_match(SessionLocal, status="rejected")

    resp = test_client.post(f"/patients/matches/{match_id}/outreach")
    assert "error" in resp.json()


def test_outreach_on_nonexistent_match_returns_error(client):
    test_client, _ = client
    resp = test_client.post("/patients/matches/99999/outreach")
    assert "error" in resp.json()


def test_outreach_handles_llm_failure_gracefully(client, monkeypatch):
    test_client, SessionLocal = client
    match_id = _make_match(SessionLocal, status="approved")

    def failing_ask_llm(*a, **k):
        raise RuntimeError("simulated API failure")

    monkeypatch.setattr(patients_module, "ask_llm", failing_ask_llm)

    resp = test_client.post(f"/patients/matches/{match_id}/outreach")
    assert "error" in resp.json()

    db = SessionLocal()
    match = db.query(models.PatientMatch).filter(models.PatientMatch.id == match_id).first()
    assert match.outreach_draft == "", "A failed generation must not leave a partial/corrupt draft"
    assert match.status == "approved", "Status must be unaffected by a generation failure"
    db.close()
