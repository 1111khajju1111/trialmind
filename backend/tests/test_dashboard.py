"""
Tests for the Priority 2 SIH "Control Tower" additions to
GET /dashboard/portfolio:
1. open_safety_signals counts only non-terminal (open/under_review)
   SafetySignal rows -- escalated/dismissed signals are resolved, not
   "open" for a control-tower glance.
2. regulatory_alert_count and monitoring_alert_count are split out of the
   same compliance.build_alerts() feed GET /compliance/alerts uses, so a
   coordinator never sees the two dashboards disagree.

Run with: pytest tests/test_dashboard.py -v
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


def _make_study(SessionLocal, **overrides):
    db = SessionLocal()
    defaults = dict(study_code="STUDY-CT", title="Control Tower Test Study", status="active")
    defaults.update(overrides)
    study = models.Study(**defaults)
    db.add(study)
    db.commit()
    db.refresh(study)
    study_id = study.id
    db.close()
    return study_id


def _add_signal(SessionLocal, study_id, status):
    db = SessionLocal()
    signal = models.SafetySignal(
        study_id=study_id, signal_key=f"key-{status}-{study_id}", drug="Metformin",
        batch_number="BATCH-001", window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc), case_ids="[]",
        patient_count=3, case_count=3, status=status,
    )
    db.add(signal)
    db.commit()
    db.close()


def _add_overdue_milestone(SessionLocal, study_id):
    db = SessionLocal()
    db.add(models.StudyMilestone(
        study_id=study_id, milestone_type="ctri_registration", name="CTRI Registration",
        status="pending", planned_date=datetime.now(timezone.utc) - timedelta(days=3),
    ))
    db.commit()
    db.close()


def _add_overdue_monitoring_visit(SessionLocal, study_id):
    db = SessionLocal()
    db.add(models.MonitoringVisit(
        study_id=study_id, visit_date=datetime.now(timezone.utc) - timedelta(days=5),
        findings="Visit overdue.", overdue=True,
    ))
    db.commit()
    db.close()


def test_open_safety_signals_excludes_terminal_statuses(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    _add_signal(SessionLocal, study_id, "open")
    _add_signal(SessionLocal, study_id, "under_review")
    _add_signal(SessionLocal, study_id, "escalated")
    _add_signal(SessionLocal, study_id, "dismissed")

    resp = test_client.get("/dashboard/portfolio")
    assert resp.status_code == 200
    assert resp.json()["open_safety_signals"] == 2


def test_regulatory_and_monitoring_alert_counts_split_correctly(client):
    test_client, SessionLocal = client
    study_id = _make_study(SessionLocal)
    _add_overdue_milestone(SessionLocal, study_id)
    _add_overdue_monitoring_visit(SessionLocal, study_id)

    resp = test_client.get("/dashboard/portfolio")
    data = resp.json()
    assert data["regulatory_alert_count"] == 1
    assert data["monitoring_alert_count"] == 1

    # Same counts should be consistent with the underlying alert feed the
    # Regulatory page itself reads from.
    alerts = test_client.get("/compliance/alerts").json()["alerts"]
    assert sum(1 for a in alerts if a["type"] == "milestone") == data["regulatory_alert_count"]
    assert sum(1 for a in alerts if a["type"] == "monitoring") == data["monitoring_alert_count"]
