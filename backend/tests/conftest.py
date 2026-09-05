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
