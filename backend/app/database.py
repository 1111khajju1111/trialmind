from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to already-existing tables after their first deploy.
# Base.metadata.create_all() only creates missing TABLES, not missing
# COLUMNS on tables that already exist -- so a table added in an earlier
# priority (e.g. patient_matches, approval_log) needs its new columns
# added explicitly here. No Alembic in this hackathon build; this is the
# lightweight equivalent for "ADD COLUMN IF NOT EXISTS" that works on both
# SQLite and Postgres.
_ADDED_COLUMNS = {
    "trials": [
        # Priority 2 -- links a trial to a Study so PatientMatch/recruitment
        # can be traced to a study+site context. Added after `trials` was
        # first deployed.
        ("study_id", "INTEGER"),
    ],
    "patient_matches": [
        ("study_id", "INTEGER"),
        ("site_id", "INTEGER"),
        # Outreach lifecycle fields, added after `patient_matches` was
        # first deployed: outreach_sent = coordinator finalized/locked the
        # draft; email_transmitted = a real email actually went out.
        ("outreach_sent", "BOOLEAN"),
        ("email_transmitted", "BOOLEAN"),
    ],
    "approval_log": [
        ("rationale", "TEXT"),
    ],
    "studies": [
        # Priority 4 -- CTRI registration fields, added after `studies` was
        # first deployed.
        ("ctri_number", "TEXT"),
        ("ctri_status", "TEXT"),
        ("ctri_registration_date", "TIMESTAMP"),
    ],
    "study_subjects": [
        # Priority 6 -- Consent & Data Protection MVP, added after
        # `study_subjects` was first deployed.
        ("consent_status", "TEXT"),
        ("consent_version", "TEXT"),
        ("consent_date", "TIMESTAMP"),
    ],
}


def run_lightweight_migrations():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all() will create it fresh with all columns
            existing_columns = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name in existing_columns:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
