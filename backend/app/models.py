from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    condition = Column(String)
    biomarkers = Column(Text)  # comma separated for demo simplicity
    location = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Trial(Base):
    __tablename__ = "trials"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    condition = Column(String)
    criteria = Column(Text)  # raw inclusion/exclusion protocol text
    structured_criteria = Column(Text)  # JSON list of deterministic rules, extracted by the LLM
    # A Trial IS the "Protocol" in CTMS terms. This links it to its parent
    # Study so existing TrialMind protocol ingestion / eligibility / matching
    # can be scoped to a study, per the SIH26046 first-shot plan. Nullable so
    # existing seeded/legacy trials created before Study existed still work.
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Study(Base):
    """CTMS core: the top-level clinical study. A Study has one active
    protocol (a Trial) plus Sites, Milestones, Deviations, Monitoring
    Visits, and per-subject enrollment (StudySubject, linking Patients into
    this study's recruitment funnel -- see app/services/recruitment.py).
    The counters below are derived from StudySubject rows rather than
    maintained by hand once subjects exist for a study; they stay on the
    model as a cheap read path for the portfolio dashboard."""
    __tablename__ = "studies"
    id = Column(Integer, primary_key=True, index=True)
    study_code = Column(String, unique=True, index=True, nullable=False)  # e.g. "STUDY-001"
    title = Column(String, nullable=False)
    phase = Column(String)  # e.g. "Phase II", "Phase III"
    intervention = Column(String)
    principal_investigator = Column(String)
    target_enrollment = Column(Integer, default=0)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="planning")  # planning, active, paused, completed, terminated

    # Recruitment funnel counters -- derived from StudySubject, see
    # app/services/recruitment.py:recompute_recruitment
    screened_count = Column(Integer, default=0)
    eligible_count = Column(Integer, default=0)
    enrolled_count = Column(Integer, default=0)
    randomized_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    withdrawn_count = Column(Integer, default=0)

    # Priority 4 -- CTRI registration, tracked as first-class fields
    # (rather than only as a StudyMilestone) because a study has exactly
    # one CTRI number/status, not a repeatable event. Kept in sync with the
    # regulatory timeline's "ctri_registration" milestone by
    # routers/studies.py:update_ctri.
    ctri_number = Column(String, nullable=True)
    ctri_status = Column(String, default="not_registered")  # not_registered, pending, registered
    ctri_registration_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    site_code = Column(String, index=True)  # e.g. "SITE-01"
    institution = Column(String, nullable=False)
    pi_name = Column(String)  # site-level PI, may differ from study PI
    coordinator_name = Column(String)
    activation_status = Column(String, default="pending")  # pending, activated, closed
    enrollment_target = Column(Integer, default=0)
    activated_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudyMilestone(Base):
    """IEC approval, CTRI registration, site activation, first/last patient,
    close-out, etc. planned_date/actual_date drives the due-date alerting
    used by the compliance dashboard."""
    __tablename__ = "study_milestones"
    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    milestone_type = Column(String, nullable=False)  # iec_approval, ctri_registration, site_activation,
                                                       # first_patient_in, last_patient_in, close_out, other
    name = Column(String, nullable=False)
    planned_date = Column(DateTime(timezone=True), nullable=True)
    actual_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="pending")  # pending, completed, overdue
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProtocolDeviation(Base):
    __tablename__ = "protocol_deviations"
    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    description = Column(Text, nullable=False)
    severity = Column(String, default="minor")  # minor, major, critical
    deviation_date = Column(DateTime(timezone=True), nullable=True)
    resolution_status = Column(String, default="open")  # open, under_review, resolved
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MonitoringVisit(Base):
    __tablename__ = "monitoring_visits"
    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    visit_date = Column(DateTime(timezone=True), nullable=True)
    findings = Column(Text)
    overdue = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudySubject(Base):
    """Links an existing Patient into a Study's recruitment funnel at a
    given Site. This is the missing piece between TrialMind's Patient
    directory and CTMS-level recruitment tracking: Study.*_count fields are
    derived from these rows (see app/services/recruitment.py) rather than
    maintained by hand once subjects exist for a study."""
    __tablename__ = "study_subjects"
    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    subject_code = Column(String, nullable=True)  # e.g. pseudonymous "SUBJ-0001"
    # screened -> eligible -> enrolled -> randomized -> completed, with
    # withdrawn as a terminal side-branch reachable from any stage.
    status = Column(String, default="screened")
    enrolled_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Priority 6 -- Consent & Data Protection MVP. Kept as a distinct
    # lifecycle from `status` (screened/eligible/enrolled/...): a subject
    # can be withdrawn from the study for reasons unrelated to consent, and
    # consent_status can independently move to "withdrawn" (DPDP-style
    # right to withdraw) without that alone changing recruitment status.
    consent_status = Column(String, default="not_obtained")  # not_obtained, obtained, withdrawn
    consent_version = Column(String, nullable=True)  # e.g. "ICF v2.1"
    consent_date = Column(DateTime(timezone=True), nullable=True)


class ProtocolChunk(Base):
    """A chunk of a trial protocol document, used as the retrieval unit for RAG.
    Embeddings are computed on the fly with TF-IDF over a trial's chunks at query
    time (lightweight, no external embedding API needed for the demo)."""
    __tablename__ = "protocol_chunks"
    id = Column(Integer, primary_key=True, index=True)
    trial_id = Column(Integer, ForeignKey("trials.id"))
    chunk_index = Column(Integer)
    content = Column(Text)


class AgentAction(Base):
    """Records every step the agent takes for a given run, powering the
    action timeline / audit trail UI."""
    __tablename__ = "agent_actions"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)  # groups all steps of one agent run
    trial_id = Column(Integer, ForeignKey("trials.id"), nullable=True)
    step_name = Column(String)  # e.g. "search_patients", "evaluate_eligibility"
    detail = Column(Text)  # human-readable summary of what happened
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class PatientMatch(Base):
    __tablename__ = "patient_matches"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    trial_id = Column(Integer, ForeignKey("trials.id"))
    # Priority 2: stamped at run-start time from trial.study_id / the
    # coordinator's chosen site, so every AI recommendation is traceable to
    # the exact study+site recruitment context it was generated for (not
    # just "somewhere in the whole patient database"). Nullable so matches
    # created against a legacy trial with no study link still work.
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    run_id = Column(String, index=True, nullable=True)
    fit_score = Column(Float)
    verdict = Column(String, default="VERIFICATION_REQUIRED")  # ELIGIBLE, NOT_ELIGIBLE, POTENTIAL_MATCH, VERIFICATION_REQUIRED
    rationale = Column(Text)
    outreach_draft = Column(Text)
    criteria_results = Column(Text)  # JSON: per-criterion pass/fail/missing, for the checklist UI
    missing_info = Column(Text)  # JSON list of fields the deterministic engine couldn't verify
    evidence = Column(Text)  # JSON list of {chunk_text, relevance} retrieved from the protocol
    status = Column(String, default="pending_review")  # pending_review, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    outreach_sent = Column(Boolean, default=False)  # "finalized/locked", not necessarily transmitted
    email_transmitted = Column(Boolean, default=False)  # True only if a real email actually went out via Resend


class SafetyCase(Base):
    """Priority 3 -- Pharmacovigilance MVP. A single AE/SAE case tied to a
    study (and optionally a site) and the patient it was observed in.
    is_serious/seriousness follow ICH E2A-style categories; report_due_date
    is stamped at creation time by the deadline engine
    (app/services/safety.py) so overdue/approaching-due reporting can be
    computed on read without a background job, the same pattern used for
    StudyMilestone overdue detection."""
    __tablename__ = "safety_cases"
    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)

    event_term = Column(String, nullable=False)  # short description of the AE/SAE
    event_date = Column(DateTime(timezone=True), nullable=False)

    is_serious = Column(Boolean, default=False)  # derived from `seriousness` at creation time
    severity = Column(String, default="mild")  # mild, moderate, severe
    # not_serious, death, life_threatening, hospitalization, disability, other_serious
    seriousness = Column(String, default="not_serious")
    outcome = Column(String, default="unknown")  # recovered, recovering, not_recovered, fatal, unknown
    causality = Column(String, default="unassessed")  # unrelated, unlikely, possible, probable, definite, unassessed

    status = Column(String, default="draft")  # draft, under_review, reported, closed
    narrative = Column(Text, nullable=True)

    report_due_date = Column(DateTime(timezone=True), nullable=True)
    reported_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RegulatoryDraft(Base):
    __tablename__ = "regulatory_drafts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    section = Column(String)  # e.g. "CTD Module 2.5 Clinical Overview"
    source_summary = Column(Text)
    draft_content = Column(Text)
    status = Column(String, default="pending_review")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LabEquipment(Base):
    __tablename__ = "lab_equipment"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    equipment_type = Column(String)
    status = Column(String, default="available")  # available, booked, maintenance


class Sample(Base):
    __tablename__ = "samples"
    id = Column(Integer, primary_key=True, index=True)
    label = Column(String)
    priority = Column(String, default="normal")  # normal, high, urgent
    storage_temp_c = Column(Float)
    required_temp_c = Column(Float)
    equipment_id = Column(Integer, ForeignKey("lab_equipment.id"), nullable=True)
    scheduled_time = Column(DateTime(timezone=True), nullable=True)
    breach_alert = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApprovalLog(Base):
    __tablename__ = "approval_log"
    id = Column(Integer, primary_key=True, index=True)
    module = Column(String)  # patient_matching, regulatory, lab_scheduling
    record_id = Column(Integer)
    action = Column(String)  # approved, rejected
    actor = Column(String, default="demo_user")
    # Priority 2: "store AI action, reviewer, timestamp, decision AND
    # RATIONALE in the audit trail." For patient_matching this is seeded
    # from the AI's own PatientMatch.rationale at decision time (the "AI
    # action" being reviewed) with the reviewer's optional note appended, so
    # the audit trail always explains *why* a decision was made, not just
    # what the decision was.
    rationale = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
