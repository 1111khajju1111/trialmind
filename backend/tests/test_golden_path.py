"""
Golden-path end-to-end test: the exact flow the V6 demo script promises --
reset to seeded state, run the agent on LIPID-2, confirm A. Torres reaches
ELIGIBLE with evidence, approve her, generate an outreach draft, and confirm
the audit timeline records the whole thing. If this test breaks, the demo
is broken.

Also covers the NOT_ELIGIBLE approval safety boundary added alongside it:
a deterministically NOT_ELIGIBLE candidate must never be approvable, at the
API level, regardless of what the UI shows.

Mocks the Groq client (no network/API key needed) but exercises the real
HTTP layer, the real background-task agent run, the real deterministic
eligibility engine, and the real seed data from mock_data.py.

Run with: pytest tests/test_golden_path.py -v
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models, mock_data
from app.main import app
import app.routers.patients as patients_module
import app.services.agent_orchestrator as orchestrator_module


class FakeFunction:
    def __init__(self, name, arguments_dict):
        self.name = name
        self.arguments = json.dumps(arguments_dict)


class FakeToolCall:
    def __init__(self, name, arguments_dict, call_id):
        self.id = call_id
        self.function = FakeFunction(name, arguments_dict)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


def _make_scripted_llm(hyperlipidemia_patients):
    """Scripts the same tool-calling sequence a real Llama run would
    plausibly make for LIPID-2: search, evaluate everyone with the
    condition, pull evidence for each, then a final text-only ranking call
    (agent_orchestrator._generate_final_ranking is a separate, tools-less
    completion -- see call 4)."""
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        n = call_count["n"]
        tools_requested = "tools" in kwargs and kwargs["tools"]

        if n == 1:
            return FakeResponse(FakeMessage(tool_calls=[
                FakeToolCall("search_patients", {"condition": "Hyperlipidemia"}, "t1"),
            ]))
        if n == 2:
            calls = [
                FakeToolCall("evaluate_eligibility", {"patient_id": p.id}, f"e{p.id}")
                for p in hyperlipidemia_patients
            ]
            return FakeResponse(FakeMessage(tool_calls=calls))
        if n == 3:
            calls = [
                FakeToolCall("retrieve_evidence",
                              {"patient_id": p.id, "query": "LDL cholesterol eligibility"},
                              f"ev{p.id}")
                for p in hyperlipidemia_patients
            ]
            return FakeResponse(FakeMessage(tool_calls=calls))
        if n == 4 and tools_requested:
            # Tool-calling loop is done (agent decided no more tools needed).
            return FakeResponse(FakeMessage(content="", tool_calls=None))

        # Final text-only ranking call (_generate_final_ranking) -- no
        # `tools` kwarg present, matches the fixed code path.
        final = json.dumps([
            {"patient_id": p.id, "rationale": f"{p.name} meets all LIPID-2 inclusion criteria."}
            for p in hyperlipidemia_patients
        ])
        return FakeResponse(FakeMessage(content=final, tool_calls=None))

    return fake_create


@pytest.fixture
def golden_client(monkeypatch):
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

    # The /match/start background task opens its own session via the
    # module-level SessionLocal (by design -- BackgroundTasks outlive the
    # request's dependency-injected session), which does NOT go through
    # get_db's override. Point it at the same in-memory test engine so the
    # background-run actually lands in the DB this test can see.
    monkeypatch.setattr(patients_module, "SessionLocal", TestSessionLocal)

    # Seed the real demo dataset directly (not via /admin/reset -- that
    # endpoint is demo_mode-gated and exercised separately; this test wants
    # the seeded data, not the HTTP wrapper around it).
    seed_db = TestSessionLocal()
    mock_data.seed_if_empty(seed_db)
    seed_db.close()

    test_client = TestClient(app)
    yield test_client, TestSessionLocal
    app.dependency_overrides.clear()


def test_golden_path_lipid2_torres_eligible_to_audit(golden_client, monkeypatch):
    client, SessionLocal = golden_client

    # ---- find the seeded LIPID-2 trial and its condition's patients ----
    trials_resp = client.get("/trials/")
    lipid2 = next((t for t in trials_resp.json() if t["name"] == "LIPID-2 Trial"), None)
    assert lipid2 is not None, "Seed data must include the LIPID-2 Trial (hero demo path)."

    db = SessionLocal()
    hyperlipidemia_patients = db.query(models.Patient).filter(
        models.Patient.condition == "Hyperlipidemia"
    ).all()
    torres = next((p for p in hyperlipidemia_patients if p.name == "A. Torres"), None)
    db.close()
    assert torres is not None, "Seed data must include patient A. Torres (hero demo path)."

    # ---- mock the LLM, run the agent on LIPID-2 ----
    fake_create = _make_scripted_llm(hyperlipidemia_patients)
    monkeypatch.setattr(
        orchestrator_module.client, "chat",
        type("C", (), {"completions": type("Comp", (), {"create": staticmethod(fake_create)})()})(),
    )

    start_resp = client.post("/patients/match/start", json={"trial_id": lipid2["id"]})
    assert start_resp.status_code == 200
    run_id = start_resp.json()["run_id"]
    assert run_id  # item 10: a run ID must be returned/associated with the run

    # ---- A. Torres reaches ELIGIBLE with 4/4 machine-checkable criteria passing ----
    matches_resp = client.get("/patients/matches", params={"run_id": run_id})
    matches = matches_resp.json()
    torres_match = next((m for m in matches if m["patient_id"] == torres.id), None)
    assert torres_match is not None, "A. Torres must have a match record after the run."
    assert torres_match["verdict"] == "ELIGIBLE"
    assert torres_match["run_id"] == run_id  # item 10: patient/trial context tied to the run
    passed = [c for c in torres_match["criteria_results"] if c["status"] == "pass"]
    assert len(passed) == len(torres_match["criteria_results"]) >= 4
    assert torres_match["missing_info"] == []

    # ---- evidence is patient-scoped and inspectable ----
    assert len(torres_match["evidence"]) > 0
    for e in torres_match["evidence"]:
        assert "chunk_id" in e and "relevance" in e

    # ---- human approval required before outreach ----
    outreach_before_approval = client.post(f"/patients/matches/{torres_match['id']}/outreach")
    assert "error" in outreach_before_approval.json()

    approve_resp = client.post("/approvals/", json={
        "module": "patient_matching", "record_id": torres_match["id"], "action": "approved",
    })
    assert approve_resp.json().get("ok") is True

    log_resp = client.get("/approvals/log")
    log_entry = next((l for l in log_resp.json() if l["record_id"] == torres_match["id"]), None)
    assert log_entry is not None
    assert log_entry["action"] == "approved"
    assert log_entry["actor"]  # item 17: coordinator/actor recorded

    # ---- outreach stays a draft, never auto-sent ----
    monkeypatch.setattr(patients_module, "ask_llm", lambda *a, **k: "Dear Dr. Smith, referring A. Torres...")
    draft_resp = client.post(f"/patients/matches/{torres_match['id']}/outreach")
    draft = draft_resp.json()
    assert draft["outreach_draft"]
    assert draft["outreach_sent"] is False
    assert draft["outreach_status"] == "DRAFT"

    send_resp = client.post(
        f"/patients/matches/{torres_match['id']}/send-outreach",
        json={"to_email": "physician@example.com"},
    )
    send_json = send_resp.json()
    assert "NOT SENT" in send_json["message"]
    assert send_json["match"]["outreach_sent"] is True  # finalized/locked, not actually emailed
    assert send_json["match"]["outreach_status"] == "FINALIZED"
    assert send_json["match"]["email_transmitted"] is False

    # ---- audit timeline records the complete flow with a run ID ----
    timeline_resp = client.get(f"/audit/timeline/{run_id}")
    steps = {s["step_name"] for s in timeline_resp.json()}
    for expected in ("run_started", "protocol_loaded", "search_patients", "evaluate_eligibility", "run_completed"):
        assert expected in steps, f"Audit timeline missing expected step '{expected}'."
    for s in timeline_resp.json():
        assert s["run_id"] == run_id
        assert s["timestamp"] is not None  # item 19: WHEN


def test_not_eligible_candidate_cannot_be_approved(golden_client):
    """Safety boundary (item 20): a deterministically NOT_ELIGIBLE match can
    never be approved through the API, regardless of what any client sends."""
    client, SessionLocal = golden_client
    db = SessionLocal()
    trial = db.query(models.Trial).filter(models.Trial.name == "LIPID-2 Trial").first()
    patient = db.query(models.Patient).filter(models.Patient.condition == "Hyperlipidemia").first()
    match = models.PatientMatch(
        patient_id=patient.id, trial_id=trial.id, run_id="manual-test",
        fit_score=0.0, verdict="NOT_ELIGIBLE", rationale="test",
        outreach_draft="", status="pending_review",
        criteria_results="[]", missing_info="[]", evidence="[]",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    match_id = match.id
    db.close()

    resp = client.post("/approvals/", json={
        "module": "patient_matching", "record_id": match_id, "action": "approved",
    })
    body = resp.json()
    assert "error" in body
    assert "NOT_ELIGIBLE" in body["error"] or "cannot be approved" in body["error"]

    db = SessionLocal()
    refreshed = db.query(models.PatientMatch).filter(models.PatientMatch.id == match_id).first()
    assert refreshed.status == "pending_review"  # unchanged -- the approval never took effect
    db.close()
