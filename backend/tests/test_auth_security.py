"""
P1 security verification -- the exact scenarios called out in review:

  1. No token                                    -> 401
  2. Invalid token                                -> 401
  3. Valid Coordinator token                      -> Coordinator permissions
  4. Valid Regulator token                        -> GET allowed, POST/PATCH/DELETE -> 403
  5. Coordinator token + X-User-Role: Administrator -> still Coordinator (header can't escalate)
  6. No token + X-User-Role: Administrator        -> 401 when DEMO_MODE=false

This file forces DEMO_MODE=false for every test in it (see the client
fixture below), unlike the rest of the suite -- these tests exist
specifically to prove the "real auth required" path works, so they run
with the demo_mode fallback deliberately turned off, not relying on the
conftest.py default that keeps the rest of the suite passing.

Run with: pytest tests/test_auth_security.py -v
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
from app.config import settings
from app.main import app


@pytest.fixture
def client():
    # Force the real-auth path for this file regardless of the
    # conftest.py-wide DEMO_MODE=true default -- these tests are exactly
    # the ones meant to prove the fallback being OFF works correctly.
    original_demo_mode = settings.demo_mode
    settings.demo_mode = False

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
    yield test_client
    app.dependency_overrides.clear()
    settings.demo_mode = original_demo_mode


def _login(client, username, password="trialmind123"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


# A representative sample of protected endpoints across the previously
# "thin" routers (dashboard/audit/interop/compliance/lab, now
# router-level-protected) plus a couple of the specific ones named in the
# original review (patients, studies). Not exhaustive -- exhaustive
# per-route coverage belongs in each router's own test file -- but broad
# enough to prove the auth *mechanism* itself, which is what's being
# verified here, not any one route's business logic.
PROTECTED_GET_ROUTES = [
    "/dashboard/portfolio",
    "/audit/runs",
    "/interop/mapping",
    "/compliance/alerts",
    "/lab/samples",
    "/patients/",
    "/studies/",
    "/trials/",
    "/safety/signals",
    "/regulatory/drafts",
    "/approvals/log",
]


class TestNoToken:
    """1. No token -> 401 on protected routes."""

    def test_no_token_rejected_on_dashboard(self, client):
        resp = client.get("/dashboard/portfolio")
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", PROTECTED_GET_ROUTES)
    def test_no_token_rejected_everywhere(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should 401 with no token, got {resp.status_code}"

    def test_no_token_rejected_on_write_endpoint(self, client):
        resp = client.post("/regulatory/draft", json={
            "title": "t", "section": "s", "source_summary": "x",
        })
        assert resp.status_code == 401


class TestInvalidToken:
    """2. Invalid/garbage token -> 401."""

    def test_garbage_bearer_token_rejected(self, client):
        resp = client.get(
            "/dashboard/portfolio",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_malformed_authorization_header_rejected(self, client):
        # Missing "Bearer " scheme prefix entirely.
        resp = client.get(
            "/dashboard/portfolio",
            headers={"Authorization": "just-a-raw-token-with-no-scheme"},
        )
        assert resp.status_code == 401


class TestValidCoordinatorToken:
    """3. Valid Study Coordinator token -> Coordinator-level permissions."""

    def test_coordinator_can_read_protected_routes(self, client):
        token = _login(client, "coordinator")
        headers = {"Authorization": f"Bearer {token}"}
        for path in PROTECTED_GET_ROUTES:
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"{path} -> {resp.status_code}, {resp.text}"

    def test_coordinator_can_submit_approval_role(self, client):
        # submit_approval requires Principal Investigator or Study
        # Coordinator -- Coordinator should pass the role gate (the
        # record-not-found 200 is fine; what matters is it's not a 403).
        token = _login(client, "coordinator")
        resp = client.post(
            "/approvals/",
            json={"module": "patient_matching", "record_id": 999999, "action": "approved"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 403
        assert resp.status_code != 401

    def test_coordinator_cannot_do_pharmacovigilance_only_action(self, client):
        # PATCH /safety/signals/{id}/status is Pharmacovigilance-only.
        token = _login(client, "coordinator")
        resp = client.patch(
            "/safety/signals/1/status",
            json={"status": "under_review"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestValidRegulatorToken:
    """4. Valid Regulator token -> GET allowed, mutating verbs -> 403."""

    def test_regulator_get_allowed(self, client):
        token = _login(client, "regulator")
        headers = {"Authorization": f"Bearer {token}"}
        for path in PROTECTED_GET_ROUTES:
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"{path} -> {resp.status_code}"

    def test_regulator_post_forbidden(self, client):
        token = _login(client, "regulator")
        resp = client.post(
            "/regulatory/draft",
            json={"title": "t", "section": "s", "source_summary": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_regulator_patch_forbidden(self, client):
        token = _login(client, "regulator")
        resp = client.patch(
            "/studies/1/recruitment",
            json={"screened_count": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_regulator_delete_forbidden(self, client):
        token = _login(client, "regulator")
        resp = client.delete(
            "/studies/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Either the route doesn't exist (404/405) or it's blocked by the
        # read-only gate (403) -- what must NOT happen is a successful
        # mutation (2xx) under a read-only role.
        assert resp.status_code in (403, 404, 405)


class TestHeaderCannotEscalate:
    """5. Coordinator token + X-User-Role: Administrator -> still Coordinator.

    The whole point of moving authorization onto the session: a valid
    session's role is authoritative, and the client-declared X-User-Role
    header is ignored once a real bearer token is present -- it can no
    longer be used to escalate privileges."""

    def test_forged_admin_header_does_not_escalate_coordinator(self, client):
        token = _login(client, "coordinator")
        # Administrator-only: POST /admin/reset.
        resp = client.post(
            "/admin/reset",
            headers={
                "Authorization": f"Bearer {token}",
                "X-User-Role": "Administrator",
            },
        )
        # Still resolved as Coordinator server-side -- Administrator-only
        # action must be forbidden despite the forged header. (403 for the
        # role check; demo_mode's own separate gate on /admin/reset would
        # otherwise also block it, but that's not what this test is
        # checking -- it's checking the role resolution specifically.)
        assert resp.status_code == 403

    def test_forged_admin_header_does_not_bypass_pv_only_action(self, client):
        token = _login(client, "coordinator")
        resp = client.patch(
            "/safety/signals/1/status",
            json={"status": "under_review"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-User-Role": "Administrator",
            },
        )
        assert resp.status_code == 403


class TestNoTokenHeaderOnlyRejectedWhenNotDemoMode:
    """6. No token + X-User-Role: Administrator -> 401 when DEMO_MODE=false.

    This is the forgery this whole fix closes: previously a bare header
    with no login at all was enough to act as any role."""

    def test_header_only_admin_claim_rejected(self, client):
        resp = client.post(
            "/admin/reset",
            headers={"X-User-Role": "Administrator"},
        )
        assert resp.status_code == 401

    def test_header_only_claim_rejected_on_protected_get(self, client):
        resp = client.get(
            "/dashboard/portfolio",
            headers={"X-User-Role": "Administrator"},
        )
        assert resp.status_code == 401
