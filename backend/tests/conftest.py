import sys
import os

# The existing test suite authenticates purely via the legacy X-User-Role
# header (no /auth/login call), which is only trusted as a fallback when
# settings.demo_mode is true (see app/rbac.py) -- production now defaults
# demo_mode to false, which would otherwise make every require_role()
# dependency 401 in these tests. setdefault() so an explicit
# DEMO_MODE=false in the test runner's environment (e.g. to deliberately
# test the "real auth required" path) still wins.
os.environ.setdefault("DEMO_MODE", "true")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.fixture
def test_engine():
    """Fresh, isolated database engine for one test function.

    Defaults to an in-memory SQLite engine (fast, and isolated for free --
    a brand new SQLite :memory: database per engine instance, no cleanup
    needed). Set TEST_DATABASE_URL to a real PostgreSQL URL to run the
    exact same suite against Postgres instead -- e.g.
    postgresql://user:pass@localhost:5432/trialmind_test

    This matters because SQLite and Postgres genuinely don't behave
    identically: JSON column handling, array/enum types, case-sensitivity
    of text comparisons, and constraint enforcement can all differ. A
    suite that's 100% green against SQLite can still break against the
    Postgres the app actually runs on in production (see requirements.txt's
    psycopg2-binary, and DATABASE_URL in the deployed environment) -- this
    fixture is what lets the *same* test files catch that class of bug,
    instead of only ever exercising SQLite.

    Every test file's `client`/`db_session` fixture requests this fixture
    and uses the engine it yields, rather than each file hard-coding its
    own `create_engine("sqlite:///:memory:", ...)` -- so switching the
    whole suite to Postgres is one environment variable, not an edit to
    every test file.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from app.database import Base

    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
        # Unlike a fresh sqlite :memory: engine (isolated automatically,
        # since it's a brand new database), a Postgres URL points at a
        # persistent database that earlier test runs may have left rows
        # in. Drop everything first so this test function still gets the
        # same "starts from a genuinely empty database" guarantee the rest
        # of the suite relies on for its assertions (row counts, etc).
        Base.metadata.drop_all(bind=engine)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    try:
        yield engine
    finally:
        engine.dispose()
