"""
Priority 5 -- Role-Based Access + Audit.

Role now comes from an authenticated session (see app/auth.py), not from a
client-declared header. Previously `X-User-Role` alone was trusted, which
meant any caller could set `X-User-Role: Administrator` on a request
without ever having logged in as one -- the login system added on top of
this added a real front door but didn't make the backend actually check
whether anyone had walked through it.

The rule now is:
  - If a request carries a valid `Authorization: Bearer <token>` from a
    completed /auth/login, that session's role is authoritative --
    `X-User-Role` is ignored for authorization decisions entirely.
  - If there's no valid session, the request is rejected with 401 UNLESS
    `settings.demo_mode` is true, in which case the legacy header-trust
    behavior applies (so the existing test suite and a fully-offline demo
    deployment don't require every call site to log in first). Production
    deployments should run with `demo_mode=false` (now the default -- see
    config.py), which closes this fallback entirely.
"""
from fastapi import Header, HTTPException, Request

from app import auth
from app.config import settings

# The seven roles required by SIH26046 Priority 5.
ROLES = [
    "Principal Investigator",
    "Study Coordinator",
    "Monitor",
    "Ethics Committee",
    "Pharmacovigilance",
    "Administrator",
    "Regulator",
]

# Regulator is explicitly "read-only" per the problem statement -- enforced
# globally here rather than per-route, so no future write endpoint can
# accidentally forget to exclude it.
READ_ONLY_ROLES = {"Regulator"}

DEFAULT_ROLE = "Study Coordinator"


def _header_role(x_user_role: str | None) -> str:
    """Legacy, unauthenticated resolution: trusts whatever the client sent.
    Only ever used as a demo_mode fallback when there's no valid session --
    never as the sole gate for require_role()."""
    if x_user_role in ROLES:
        return x_user_role
    return DEFAULT_ROLE


def resolve_authenticated_role(
    authorization: str | None, x_user_role: str | None
) -> str:
    """The real gate: resolves a role from an actual logged-in session.
    Raises 401 if there isn't one, unless demo_mode allows the legacy
    header fallback."""
    session = auth.session_from_authorization_header(authorization)
    if session:
        return session["role"]
    if settings.demo_mode:
        return _header_role(x_user_role)
    raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")


def require_role(*allowed_roles: str):
    """FastAPI dependency factory: raises 401 if the caller isn't logged in
    (and demo_mode doesn't allow the header fallback), or 403 unless the
    resolved role is one of `allowed_roles`. Administrator can always act
    as a superuser-style fallback. Call with no roles (`require_role()`) to
    require only that *some* authenticated user is making the request,
    without restricting to specific roles.

    Read-only roles (currently just Regulator) are blocked from every
    mutating verb (anything but GET/HEAD/OPTIONS) here too, regardless of
    `allowed_roles` -- this used to live in a separate global middleware in
    main.py that re-derived the role from the raw X-User-Role header
    (independent of session auth, and racing ahead of this dependency on
    every request including unauthenticated ones). Folding it in here
    means there's exactly one place that resolves "who is this request
    authenticated as" and exactly one place that decides what they're
    allowed to do with that identity."""

    def _dependency(
        request: Request,
        authorization: str | None = Header(default=None),
        x_user_role: str | None = Header(default=None),
    ):
        role = resolve_authenticated_role(authorization, x_user_role)
        if role in READ_ONLY_ROLES and request.method not in ("GET", "HEAD", "OPTIONS"):
            raise HTTPException(
                status_code=403,
                detail=f"The '{role}' role has read-only access and cannot perform this action.",
            )
        if not allowed_roles:
            return role
        if role == "Administrator":
            return role
        if role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Role '{role}' is not permitted to perform this action. "
                    f"Requires one of: {', '.join(allowed_roles)}."
                ),
            )
        return role

    return _dependency
