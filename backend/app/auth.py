"""
Role-based LOGIN authentication (demo-appropriate, but a real login this
time -- not just a client-side role picker).

Each of the seven RBAC roles (see app/rbac.py) gets one demo account. A
user signs in with a username/password, the backend issues an opaque
bearer token tied to that account's role, and every subsequent request
carries the token (Authorization: Bearer ...) plus the resolved role
(X-User-Role, unchanged from before) so app/rbac.py's existing
role-enforcement keeps working exactly as it did.

Tokens are held in memory (fine for a single-process demo/hackathon
deployment). A restart invalidates all sessions, which is the correct
behavior here -- there is no persistent session store.
"""
import hashlib
import hmac
import secrets
import time

from fastapi import Header, HTTPException

from app.config import settings

# username -> {password, role, display_name}
# One demo account per RBAC role. Passwords are intentionally simple demo
# credentials, not production secrets -- this whole module exists to
# demonstrate role-based login, not to protect real patient data.
DEMO_USERS = {
    "pi": {"password": "trialmind123", "role": "Principal Investigator", "display_name": "Dr. Anjali Rao"},
    "coordinator": {"password": "trialmind123", "role": "Study Coordinator", "display_name": "Study Coordinator"},
    "monitor": {"password": "trialmind123", "role": "Monitor", "display_name": "Clinical Monitor"},
    "ethics": {"password": "trialmind123", "role": "Ethics Committee", "display_name": "Ethics Committee"},
    "pharmacovigilance": {"password": "trialmind123", "role": "Pharmacovigilance", "display_name": "Pharmacovigilance Officer"},
    "admin": {"password": "trialmind123", "role": "Administrator", "display_name": "Administrator"},
    "regulator": {"password": "trialmind123", "role": "Regulator", "display_name": "Regulator (read-only)"},
}

# token -> {username, role, issued_at}
ACTIVE_SESSIONS: dict[str, dict] = {}

TOKEN_TTL_SECONDS = 12 * 60 * 60  # 12 hours


def _hash_password(password: str) -> str:
    return hmac.new(settings.auth_secret.encode(), password.encode(), hashlib.sha256).hexdigest()


def verify_credentials(username: str, password: str) -> dict | None:
    user = DEMO_USERS.get((username or "").strip().lower())
    if not user:
        return None
    if not hmac.compare_digest(user["password"], password or ""):
        return None
    return user


def issue_token(username: str, role: str) -> str:
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = {"username": username, "role": role, "issued_at": time.time()}
    return token


def revoke_token(token: str) -> None:
    ACTIVE_SESSIONS.pop(token, None)


def get_session(token: str) -> dict | None:
    session = ACTIVE_SESSIONS.get(token)
    if not session:
        return None
    if time.time() - session["issued_at"] > TOKEN_TTL_SECONDS:
        ACTIVE_SESSIONS.pop(token, None)
        return None
    return session


def get_current_session(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: requires a valid bearer token from a completed
    login, for endpoints that should be reachable only by an authenticated
    user (not just "whatever role header the client happened to send")."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    token = authorization.split(" ", 1)[1].strip()
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return session


def session_from_authorization_header(authorization: str | None) -> dict | None:
    """Same lookup as get_current_session, but returns None instead of
    raising when there's no (or an invalid) bearer token. Used by
    app/rbac.py to resolve a role from the *actual authenticated session*
    rather than trusting a client-declared X-User-Role header, which any
    caller could set to whatever it likes without ever having logged in."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return get_session(token)


def validate_demo_users_cover_all_roles() -> None:
    """Sanity check that DEMO_USERS still has exactly one account per RBAC
    role, so the two lists can't silently drift apart. Imports app.rbac
    lazily (rather than at module load time) because app.rbac itself
    imports this module -- doing the import here, called from main.py's
    startup handler once both modules are fully loaded, avoids a circular
    import between app.auth and app.rbac."""
    from app.rbac import ROLES
    assert set(u["role"] for u in DEMO_USERS.values()) == set(ROLES), "DEMO_USERS must cover every RBAC role"
