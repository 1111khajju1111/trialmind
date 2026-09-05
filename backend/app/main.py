import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, SessionLocal, run_lightweight_migrations
from app.config import settings
from app.rbac import READ_ONLY_ROLES, ROLES
from app.routers import patients, regulatory, lab, approvals, trials, audit, admin, studies, dashboard, safety, compliance, interop, auth as auth_router
from app import mock_data, auth as auth_module

logger = logging.getLogger("trialmind")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Pharma AI Agentic Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# NOTE: read-only-role enforcement (Regulator can GET but not mutate) used
# to live here as a global middleware that re-derived the role from the raw
# X-User-Role header on every request -- independent of, and racing ahead
# of, the session-based auth on each route. It's now folded into
# require_role() itself (see app/rbac.py), so every route that calls
# require_role() gets the read-only check for free, resolved the same
# authenticated way (session first, header only as a demo_mode fallback)
# as every other authorization decision. Routes that don't call
# require_role() at all were never covered by a real auth story anyway;
# see studies.py and patients.py, which now apply it at the router level.


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort safety net: any exception a router didn't already catch
    and turn into a clean {"error": ...} response lands here instead of
    reaching the client as a raw traceback or a raw database error message
    (which can leak internals like connection strings, file paths, or
    library internals). The real exception is still logged server-side --
    this only changes what the client sees."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected server error occurred. Please try again."},
    )


app.include_router(auth_router.router)
app.include_router(studies.router)
app.include_router(dashboard.router)
app.include_router(trials.router)
app.include_router(patients.router)
app.include_router(regulatory.router)
app.include_router(lab.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(admin.router)
app.include_router(safety.router)
app.include_router(compliance.router)
app.include_router(interop.router)


@app.get("/rbac/roles")
def list_roles():
    """Lets the frontend render the role switcher without hard-coding the
    role list in two places."""
    return {"roles": ROLES, "read_only_roles": sorted(READ_ONLY_ROLES)}


@app.on_event("startup")
def on_startup():
    auth_module.validate_demo_users_cover_all_roles()
    # Deployment sanity check, not a hard gate: warn loudly (don't crash --
    # a broken warning shouldn't be the thing that takes the app down) if
    # this looks like a production boot (demo_mode=false) still running the
    # placeholder secret from config.py's default / .env.example. This
    # secret signs session tokens; leaving it at the shipped default would
    # let anyone forge a valid-looking session offline.
    if not settings.demo_mode and settings.auth_secret in (
        "trialmind-demo-secret-change-me",
        "change-me-in-production",
    ):
        logger.warning(
            "AUTH_SECRET is still set to its placeholder value while "
            "DEMO_MODE=false. Set a strong random AUTH_SECRET before "
            "exposing this deployment."
        )
    try:
        Base.metadata.create_all(bind=engine)
        run_lightweight_migrations()
        db = SessionLocal()
        try:
            mock_data.seed_if_empty(db)
            mock_data.seed_additional_demo_data(db)
        finally:
            db.close()
    except Exception as e:
        # Don't crash the whole app if the DB is temporarily unreachable at
        # boot, or if this app instance is being imported for testing with
        # get_db overridden but the module-level engine/SessionLocal still
        # point at a real (possibly unconfigured) database. Endpoints that
        # actually need the DB will surface their own clear errors.
        print(f"Startup DB init/seed failed (non-fatal): {e}")


@app.get("/")
def root():
    return {"status": "ok", "service": "pharma-ai-agentic-platform"}


@app.get("/health")
def health():
    return {"status": "healthy", "demo_mode": settings.demo_mode}
