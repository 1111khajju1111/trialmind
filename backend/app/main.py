import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, SessionLocal, run_lightweight_migrations
from app.config import settings
from app.rbac import get_current_role, READ_ONLY_ROLES, ROLES
from app.routers import patients, regulatory, lab, approvals, trials, audit, admin, studies, dashboard, safety, compliance, interop
from app import mock_data

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


@app.middleware("http")
async def enforce_read_only_roles(request: Request, call_next):
    """Priority 5 -- RBAC (thin, demo-appropriate). The Regulator role is
    read-only by definition in the problem statement: enforced here, once,
    for every route, rather than per-router, so a future write endpoint
    can't accidentally forget to exclude it. See app/rbac.py for the full
    explanation of why this is header-based rather than a real auth system."""
    role = get_current_role(request.headers.get("x-user-role"))
    if role in READ_ONLY_ROLES and request.method not in ("GET", "HEAD", "OPTIONS"):
        return JSONResponse(
            status_code=403,
            content={"error": f"The '{role}' role has read-only access and cannot perform this action."},
        )
    return await call_next(request)


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
    try:
        Base.metadata.create_all(bind=engine)
        run_lightweight_migrations()
        db = SessionLocal()
        try:
            mock_data.seed_if_empty(db)
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
