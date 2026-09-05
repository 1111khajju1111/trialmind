from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/pharma_platform"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    cors_origins: str = "http://localhost:5173"

    # Resend
    resend_api_key: str = ""
    resend_from: str = "TrialMind <onboarding@resend.dev>"

    # When true: outreach never actually sends (even if resend_api_key is
    # set) and stays a labeled draft. Default is now False -- once a
    # coordinator clicks Send on an outreach draft, it goes straight out via
    # Resend (see routers/patients.send_outreach) instead of stopping at an
    # unsent "finalized" state. Set this back to true for a fully offline
    # demo where no real email should ever leave the box.
    demo_mode: bool = False

    # Simple shared secret used to sign/validate demo login tokens issued by
    # /auth/login. Not a substitute for real session infra -- see app/auth.py.
    auth_secret: str = "trialmind-demo-secret-change-me"

    class Config:
        env_file = ".env"

settings = Settings()