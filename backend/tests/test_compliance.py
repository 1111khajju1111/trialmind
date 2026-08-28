"""
Tests for Priority 4 -- Ethics + CTRI + Regulatory Compliance:
1. PATCH /studies/{id}/ctri validates ctri_status and stays in sync with a
   'ctri_registration' StudyMilestone.
2. GET /studies/{id}/regulatory-timeline classifies milestones into
   on_track / due_soon / overdue / completed correctly.
3. GET /compliance/alerts aggregates regulatory milestones, safety
   reports, and monitoring visits into one feed.
4. GET /dashboard/regulatory aggregates CTRI status and milestone counts
   across the whole portfolio.

Run with: pytest tests/test_compliance.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone

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
    test_client = TestClient(app)
    yield test_client, TestSessionLocal
    app.dependency_overrides.clear()


def _make_study(SessionLocal, **overrides):
    db = SessionLocal()
    defaults = dict(study_code="STUDY-REG", title="Regulatory Test Study", status="active")
    defaults.update(overrides)
    study = models.Study(**defaults)
    db.add(study)
    db.commit()
    db.refresh(study)
    study_id = study.id
    db.close()
    return study_id


def _add_milestone(SessionLocal, study_id, **overrides):
    db = SessionLocal()
    defaults = dict(study_id=study_id, milestone_type="iec_approval", name="IEC Approval", status="pending")
    defaults.update(overrides)
    m = models.StudyMilestone(**defaults)
    db.add(m)
    db.commit()
    db.refresh(m)
    mid = m.id
    db.close()
    return mid


# ---------- CTRI update ----------

def test_ctri_update_rejects_invalid_status(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    resp = test_client.patch(f"/studies/{study_id}/ctri", json={"ctri_status": "bogus"})
    assert resp.status_code == 400


def test_ctri_update_accepts_valid_status(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    resp = test_client.patch(f"/studies/{study_id}/ctri", json={"ctri_status": "pending", "ctri_number": "CTRI/2026/01/000123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ctri_status"] == "pending"
    assert data["ctri_number"] == "CTRI/2026/01/000123"


def test_ctri_update_404_for_missing_study(client):
    test_client, _ = client
    resp = test_client.patch("/studies/99999/ctri", json={"ctri_status": "pending"})
    assert resp.status_code == 404


def test_ctri_registered_creates_milestone(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)

    reg_date = datetime.now(timezone.utc).isoformat()
    resp = test_client.patch(
        f"/studies/{study_id}/ctri",
        json={"ctri_status": "registered", "ctri_number": "CTRI/2026/01/000123", "ctri_registration_date": reg_date},
    )
    assert resp.status_code == 200

    timeline = test_client.get(f"/studies/{study_id}/regulatory-timeline").json()
    ctri_milestones = [m for m in timeline["milestones"] if m["milestone_type"] == "ctri_registration"]
    assert len(ctri_milestones) == 1
    assert ctri_milestones[0]["status"] == "completed"
    assert ctri_milestones[0]["due_status"] is None  # completed milestones aren't alerts


def test_ctri_registered_twice_updates_not_duplicates_milestone(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    test_client.patch(f"/studies/{study_id}/ctri", json={"ctri_status": "registered"})
    test_client.patch(f"/studies/{study_id}/ctri", json={"ctri_status": "registered", "ctri_number": "CTRI/UPDATED"})

    timeline = test_client.get(f"/studies/{study_id}/regulatory-timeline").json()
    ctri_milestones = [m for m in timeline["milestones"] if m["milestone_type"] == "ctri_registration"]
    assert len(ctri_milestones) == 1


# ---------- Regulatory timeline ----------

def test_regulatory_timeline_classifies_milestones(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)

    _add_milestone(SessionLocal, study_id, milestone_type="iec_submission", name="IEC Submission",
                    planned_date=now - timedelta(days=2), status="pending")  # overdue
    _add_milestone(SessionLocal, study_id, milestone_type="iec_approval", name="IEC Approval",
                    planned_date=now + timedelta(days=5), status="pending")  # due_soon
    _add_milestone(SessionLocal, study_id, milestone_type="amendment", name="Protocol Amendment 1",
                    planned_date=now + timedelta(days=60), status="pending")  # on_track
    _add_milestone(SessionLocal, study_id, milestone_type="close_out", name="Close-out",
                    planned_date=now - timedelta(days=100), actual_date=now - timedelta(days=90), status="completed")

    resp = test_client.get(f"/studies/{study_id}/regulatory-timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == {"on_track": 1, "due_soon": 1, "overdue": 1, "completed": 1}
    by_name = {m["name"]: m for m in data["milestones"]}
    assert by_name["IEC Submission"]["due_status"] == "overdue"
    assert by_name["IEC Approval"]["due_status"] == "due_soon"
    assert by_name["Protocol Amendment 1"]["due_status"] == "on_track"
    assert by_name["Close-out"]["due_status"] is None
    assert "deadline_disclaimer" in data


def test_regulatory_timeline_404_for_missing_study(client):
    test_client, _ = client
    resp = test_client.get("/studies/99999/regulatory-timeline")
    assert resp.status_code == 404


def test_regulatory_timeline_flags_is_regulatory_correctly(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    _add_milestone(SessionLocal, study_id, milestone_type="ctri_update", name="CTRI Update", planned_date=None)
    _add_milestone(SessionLocal, study_id, milestone_type="site_activation", name="Site Activation", planned_date=None)

    data = test_client.get(f"/studies/{study_id}/regulatory-timeline").json()
    by_name = {m["name"]: m for m in data["milestones"]}
    assert by_name["CTRI Update"]["is_regulatory"] is True
    assert by_name["Site Activation"]["is_regulatory"] is False


# ---------- Compliance alerts ----------

def test_compliance_alerts_include_overdue_milestone(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)
    _add_milestone(SessionLocal, study_id, milestone_type="ctri_registration", name="CTRI Registration",
                    planned_date=now - timedelta(days=3), status="pending")

    resp = test_client.get("/compliance/alerts", params={"study_id": study_id})
    data = resp.json()
    assert data["overdue_count"] == 1
    assert data["alerts"][0]["type"] == "milestone"
    assert data["alerts"][0]["severity"] == "overdue"
    assert "deadline_disclaimer" in data


def test_compliance_alerts_exclude_on_track_and_completed(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    now = datetime.now(timezone.utc)
    _add_milestone(SessionLocal, study_id, milestone_type="amendment", name="Far-out amendment",
                    planned_date=now + timedelta(days=90), status="pending")
    _add_milestone(SessionLocal, study_id, milestone_type="iec_approval", name="Already approved",
                    planned_date=now - timedelta(days=30), actual_date=now - timedelta(days=25), status="completed")

    resp = test_client.get("/compliance/alerts", params={"study_id": study_id})
    assert resp.json()["total_count"] == 0


def test_compliance_alerts_filters_by_study(client):
    test_client, SessionLocal = client
    study_a = _make_study(SessionLocal, study_code="STUDY-A")
    study_b = _make_study(SessionLocal, study_code="STUDY-B")
    now = datetime.now(timezone.utc)
    _add_milestone(SessionLocal, study_a, planned_date=now - timedelta(days=1), status="pending")
    _add_milestone(SessionLocal, study_b, planned_date=now - timedelta(days=1), status="pending")

    resp = test_client.get("/compliance/alerts", params={"study_id": study_a})
    data = resp.json()
    assert data["total_count"] == 1
    assert data["alerts"][0]["study_id"] == study_a


# ---------- Portfolio regulatory dashboard ----------

def test_regulatory_dashboard_counts_ctri_status(client):
    test_client, SessionLocal = client
    _make_study(SessionLocal, study_code="A", ctri_status="registered")
    _make_study(SessionLocal, study_code="B", ctri_status="pending")
    _make_study(SessionLocal, study_code="C", ctri_status="not_registered")
    _make_study(SessionLocal, study_code="D")  # default not_registered

    resp = test_client.get("/dashboard/regulatory")
    data = resp.json()
    assert data["ctri_status_counts"]["registered"] == 1
    assert data["ctri_status_counts"]["pending"] == 1
    assert data["ctri_status_counts"]["not_registered"] == 2
    assert data["total_studies"] == 4


def test_regulatory_dashboard_counts_amendments(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    _add_milestone(SessionLocal, study_id, milestone_type="amendment", name="Amendment 1", status="completed", actual_date=datetime.now(timezone.utc))
    _add_milestone(SessionLocal, study_id, milestone_type="amendment", name="Amendment 2", status="pending")

    resp = test_client.get("/dashboard/regulatory")
    assert resp.json()["amendments_logged"] == 2
