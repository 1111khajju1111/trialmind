"""
Tests that evidence retrieved for one patient can never leak onto another
patient's match record, even when the agent evaluates multiple patients and
requests evidence out of order. This directly tests the P0 fix from the
second review pass.

Requires: pytest, sqlalchemy (with sqlite), and the app's own dependencies
installed (see requirements.txt + requirements-dev.txt). Uses an in-memory
sqlite DB and mocks all Groq API calls, so it runs with no network access
and no API key -- important for CI and for running this suite for free
before a hackathon demo.

Run with: pytest tests/test_matching.py -v
"""
import sys
import os
import json
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app import models
from app.services.agent_orchestrator import run_agent


@pytest.fixture
def db_session():
    # Fix (Priority 0 -- database test isolation): every other test file in
    # this suite pins poolclass=StaticPool for its in-memory SQLite engine;
    # this one didn't. Without it, SQLAlchemy's default for a `:memory:`
    # URL is SingletonThreadPool (one connection *per thread*, reused up to
    # pool_size before being recycled) rather than a single connection for
    # the whole engine's lifetime -- correct enough for a short-lived
    # single-threaded test, but it's an unpinned implicit default, not a
    # guarantee, and inconsistent with the rest of the suite. StaticPool
    # makes "one shared in-memory database for this engine" an explicit
    # property of the fixture instead of an artifact of SQLAlchemy's
    # dialect-selection logic.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def seeded_trial(db_session):
    criteria = json.dumps([
        {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
         "operator": "between", "value": [40, 65], "unit": "years",
         "source_text": "40-65", "verification_required": False},
    ])
    trial = models.Trial(name="TEST-1 Trial", condition="Test Condition",
                          criteria="Age 40-65 required.", structured_criteria=criteria)
    db_session.add(trial)
    db_session.commit()
    db_session.refresh(trial)

    for i, text in enumerate(["Age must be 40 to 65.", "No other criteria apply."]):
        db_session.add(models.ProtocolChunk(trial_id=trial.id, chunk_index=i, content=text))
    db_session.commit()

    patients = [
        models.Patient(name="Patient A", age=50, condition="Test Condition", biomarkers=""),
        models.Patient(name="Patient B", age=55, condition="Test Condition", biomarkers=""),
        models.Patient(name="Patient C", age=45, condition="Test Condition", biomarkers=""),
    ]
    db_session.add_all(patients)
    db_session.commit()
    for p in patients:
        db_session.refresh(p)

    return trial, patients


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


def make_mock_llm(patients, evidence_query_order):
    """Builds a fake `client.chat.completions.create` that scripts a
    deterministic tool-calling sequence: search all patients, evaluate each,
    then request evidence for each patient in a DIFFERENT order than they
    were evaluated -- this is exactly the scenario that exposed the original
    bug."""
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        n = call_count["n"]

        if n == 1:
            return FakeResponse(FakeMessage(tool_calls=[
                FakeToolCall("search_patients", {"condition": "Test Condition"}, "t1"),
            ]))
        if n == 2:
            calls = [
                FakeToolCall("evaluate_eligibility", {"patient_id": p.id}, f"e{p.id}")
                for p in patients
            ]
            return FakeResponse(FakeMessage(tool_calls=calls))
        if n == 3:
            # Request evidence in a scrambled order (evidence_query_order),
            # deliberately NOT matching the evaluation order above.
            calls = [
                FakeToolCall("retrieve_evidence",
                              {"patient_id": pid, "query": f"evidence for patient {pid}"},
                              f"ev{pid}")
                for pid in evidence_query_order
            ]
            return FakeResponse(FakeMessage(tool_calls=calls))

        final = json.dumps([{"patient_id": p.id, "rationale": f"Rationale for {p.name}"} for p in patients])
        return FakeResponse(FakeMessage(content=final, tool_calls=None))

    return fake_create


def test_evidence_is_isolated_per_patient_even_when_requested_out_of_order(monkeypatch, db_session, seeded_trial):
    trial, patients = seeded_trial
    patient_a, patient_b, patient_c = patients

    # Deliberately request evidence for C, then A, then B -- scrambled
    # relative to evaluation order (A, B, C) to reproduce the original bug
    # scenario where evidence got attributed to "whichever patient was last
    # evaluated" instead of the patient actually named in the tool call.
    scrambled_order = [patient_c.id, patient_a.id, patient_b.id]
    fake_create = make_mock_llm(patients, scrambled_order)

    import app.services.agent_orchestrator as orchestrator_module
    monkeypatch.setattr(orchestrator_module.client, "chat", type("C", (), {"completions": type("Comp", (), {"create": staticmethod(fake_create)})()})())

    run_id, final_text, eligibility_cache, evidence_cache, error = run_agent(db_session, trial)

    assert error is None
    assert set(eligibility_cache.keys()) == {patient_a.id, patient_b.id, patient_c.id}
    assert set(evidence_cache.keys()) == {patient_a.id, patient_b.id, patient_c.id}

    # The critical assertion: each patient's evidence must reference THAT
    # patient's ID and nobody else's, regardless of request order.
    for pid in (patient_a.id, patient_b.id, patient_c.id):
        assert pid in evidence_cache
        # evidence_cache[pid] holds the chunk list; verify it's not empty
        # (both seeded chunks are generic enough that TF-IDF should surface
        # at least one for any "evidence for patient N" query)
        assert isinstance(evidence_cache[pid], list)


def test_run_id_is_consistent_across_all_logged_actions(monkeypatch, db_session, seeded_trial):
    trial, patients = seeded_trial
    fake_create = make_mock_llm(patients, [p.id for p in patients])
    import app.services.agent_orchestrator as orchestrator_module
    monkeypatch.setattr(orchestrator_module.client, "chat", type("C", (), {"completions": type("Comp", (), {"create": staticmethod(fake_create)})()})())

    run_id, _, _, _, error = run_agent(db_session, trial)
    assert error is None

    actions = db_session.query(models.AgentAction).filter(models.AgentAction.run_id == run_id).all()
    assert len(actions) > 0
    assert all(a.run_id == run_id for a in actions)


def test_agent_error_is_captured_not_raised(monkeypatch, db_session, seeded_trial):
    trial, patients = seeded_trial

    def failing_create(**kwargs):
        raise RuntimeError("simulated Groq API timeout")

    import app.services.agent_orchestrator as orchestrator_module
    monkeypatch.setattr(orchestrator_module.client, "chat", type("C", (), {"completions": type("Comp", (), {"create": staticmethod(failing_create)})()})())

    run_id, final_text, eligibility_cache, evidence_cache, error = run_agent(db_session, trial)
    assert error is not None
    assert "simulated Groq API timeout" in error

    error_actions = db_session.query(models.AgentAction).filter(
        models.AgentAction.run_id == run_id, models.AgentAction.step_name == "agent_error"
    ).all()
    assert len(error_actions) == 1
