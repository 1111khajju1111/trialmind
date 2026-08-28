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
    # set) and stays a labeled draft, and destructive endpoints like
    # /admin/reset are reachable. Default true because this is a hackathon
    # demo build -- a real deployment handling real patient data should set
    # this to false and put proper auth in front of anything destructive.
    demo_mode: bool = True

    class Config:
        env_file = ".env"

settings = Settings()