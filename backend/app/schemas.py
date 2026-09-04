from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class PatientOut(BaseModel):
    id: int
    name: str
    age: Optional[int]
    condition: Optional[str]
    biomarkers: Optional[str]
    location: Optional[str]

    class Config:
        from_attributes = True


class TrialOut(BaseModel):
    id: int
    name: str
    condition: Optional[str]
    criteria: Optional[str]

    class Config:
        from_attributes = True


class MatchRunRequest(BaseModel):
    trial_id: int
    # Priority 2: optionally scope the candidate pool to one site within the
    # trial's linked study. study_id itself is NOT accepted here -- it is
    # always derived server-side from trial.study_id so a match can never be
    # stamped with a study the trial isn't actually linked to.
    site_id: Optional[int] = None

    class Config:
        extra = "forbid"


class PatientMatchOut(BaseModel):
    id: int
    patient_id: int
    trial_id: int
    study_id: Optional[int] = None
    site_id: Optional[int] = None
    fit_score: float
    rationale: str
    outreach_draft: str
    status: str

    class Config:
        from_attributes = True


class RegulatoryDraftRequest(BaseModel):
    title: str
    section: str
    source_summary: str

    class Config:
        extra = "forbid"


class RegulatoryDraftOut(BaseModel):
    id: int
    title: str
    section: str
    draft_content: str
    status: str

    class Config:
        from_attributes = True


class SampleOut(BaseModel):
    id: int
    label: str
    priority: str
    storage_temp_c: Optional[float]
    required_temp_c: Optional[float]
    equipment_id: Optional[int]
    scheduled_time: Optional[datetime]
    breach_alert: bool

    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    module: str
    record_id: int
    action: Literal["approved", "rejected"]
    # Optional human note captured alongside the AI's own rationale in the
    # audit trail -- e.g. why a coordinator overrode a VERIFICATION_REQUIRED
    # verdict, or rejected a POTENTIAL_MATCH.
    reviewer_note: Optional[str] = None

    class Config:
        extra = "forbid"


# ---------- Priority 1: Core CTMS ----------

class StudyCreate(BaseModel):
    study_code: str
    title: str
    phase: Optional[str] = None
    intervention: Optional[str] = None
    principal_investigator: Optional[str] = None
    target_enrollment: Optional[int] = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = "planning"
    trial_id: Optional[int] = None  # link an existing TrialMind protocol at creation time

    class Config:
        extra = "forbid"


class StudyOut(BaseModel):
    id: int
    study_code: str
    title: str
    phase: Optional[str]
    intervention: Optional[str]
    principal_investigator: Optional[str]
    target_enrollment: int
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: str
    screened_count: int
    eligible_count: int
    enrolled_count: int
    randomized_count: int
    completed_count: int
    withdrawn_count: int
    ctri_number: Optional[str] = None
    ctri_status: Optional[str] = "not_registered"
    ctri_registration_date: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecruitmentUpdate(BaseModel):
    screened_count: Optional[int] = None
    eligible_count: Optional[int] = None
    enrolled_count: Optional[int] = None
    randomized_count: Optional[int] = None
    completed_count: Optional[int] = None
    withdrawn_count: Optional[int] = None

    class Config:
        extra = "forbid"


class CTRIUpdate(BaseModel):
    """Priority 4 -- CTRI registration number, status and date, tracked as
    first-class Study fields (a study has exactly one CTRI registration,
    not a repeatable event)."""
    ctri_number: Optional[str] = None
    ctri_status: Optional[str] = None  # not_registered, pending, registered
    ctri_registration_date: Optional[datetime] = None

    class Config:
        extra = "forbid"


class SiteCreate(BaseModel):
    site_code: Optional[str] = None
    institution: str
    pi_name: Optional[str] = None
    coordinator_name: Optional[str] = None
    activation_status: Optional[str] = "pending"
    enrollment_target: Optional[int] = 0
    activated_date: Optional[datetime] = None

    class Config:
        extra = "forbid"


class SiteOut(BaseModel):
    id: int
    study_id: int
    site_code: Optional[str]
    institution: str
    pi_name: Optional[str]
    coordinator_name: Optional[str]
    activation_status: str
    enrollment_target: int
    activated_date: Optional[datetime]

    class Config:
        from_attributes = True


class MilestoneCreate(BaseModel):
    milestone_type: str
    name: str
    planned_date: Optional[datetime] = None
    actual_date: Optional[datetime] = None
    status: Optional[str] = "pending"

    class Config:
        extra = "forbid"


class MilestoneOut(BaseModel):
    id: int
    study_id: int
    milestone_type: str
    name: str
    planned_date: Optional[datetime]
    actual_date: Optional[datetime]
    status: str

    class Config:
        from_attributes = True


class DeviationCreate(BaseModel):
    site_id: Optional[int] = None
    description: str
    severity: Optional[str] = "minor"
    deviation_date: Optional[datetime] = None
    resolution_status: Optional[str] = "open"

    class Config:
        extra = "forbid"


class DeviationOut(BaseModel):
    id: int
    study_id: int
    site_id: Optional[int]
    description: str
    severity: str
    deviation_date: Optional[datetime]
    resolution_status: str

    class Config:
        from_attributes = True


class MonitoringVisitCreate(BaseModel):
    site_id: Optional[int] = None
    visit_date: Optional[datetime] = None
    findings: Optional[str] = None
    overdue: Optional[bool] = False

    class Config:
        extra = "forbid"


class MonitoringVisitOut(BaseModel):
    id: int
    study_id: int
    site_id: Optional[int]
    visit_date: Optional[datetime]
    findings: Optional[str]
    overdue: bool

    class Config:
        from_attributes = True


SUBJECT_STATUSES = Literal["screened", "eligible", "enrolled", "randomized", "completed", "withdrawn"]
# Priority 6 -- Consent & Data Protection MVP. Distinct from SUBJECT_STATUSES:
# a subject's recruitment status and their consent status can change
# independently (e.g. DPDP-style withdrawal of consent doesn't by itself
# reclassify recruitment history).
CONSENT_STATUSES = Literal["not_obtained", "obtained", "withdrawn"]


class StudySubjectCreate(BaseModel):
    patient_id: int
    site_id: Optional[int] = None
    subject_code: Optional[str] = None
    status: Optional[SUBJECT_STATUSES] = "screened"
    enrolled_date: Optional[datetime] = None
    notes: Optional[str] = None
    consent_status: Optional[CONSENT_STATUSES] = "not_obtained"
    consent_version: Optional[str] = None
    consent_date: Optional[datetime] = None

    class Config:
        extra = "forbid"


class StudySubjectUpdate(BaseModel):
    site_id: Optional[int] = None
    status: Optional[SUBJECT_STATUSES] = None
    enrolled_date: Optional[datetime] = None
    notes: Optional[str] = None
    consent_status: Optional[CONSENT_STATUSES] = None
    consent_version: Optional[str] = None
    consent_date: Optional[datetime] = None

    class Config:
        extra = "forbid"


class StudySubjectOut(BaseModel):
    id: int
    study_id: int
    site_id: Optional[int]
    patient_id: int
    subject_code: Optional[str]
    status: str
    enrolled_date: Optional[datetime]
    notes: Optional[str]
    consent_status: str = "not_obtained"
    consent_version: Optional[str] = None
    consent_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnrollSubjectRequest(BaseModel):
    enrolled_date: Optional[datetime] = None

    class Config:
        extra = "forbid"


# ---------- Priority 3: Pharmacovigilance MVP ----------

SEVERITY_VALUES = Literal["mild", "moderate", "severe"]
SERIOUSNESS_VALUES = Literal[
    "not_serious", "death", "life_threatening", "hospitalization", "disability", "other_serious"
]
OUTCOME_VALUES = Literal["recovered", "recovering", "not_recovered", "fatal", "unknown"]
CAUSALITY_VALUES = Literal["unrelated", "unlikely", "possible", "probable", "definite", "unassessed"]
SAFETY_STATUS_VALUES = Literal["draft", "under_review", "reported", "closed"]
ACTION_TAKEN_VALUES = Literal[
    "dose_not_changed", "dose_reduced", "drug_withdrawn", "drug_interrupted", "unknown"
]


class SafetyCaseCreate(BaseModel):
    study_id: int
    site_id: Optional[int] = None
    patient_id: int
    event_term: str
    event_date: Optional[datetime] = None  # defaults to now if omitted
    severity: SEVERITY_VALUES = "mild"
    seriousness: SERIOUSNESS_VALUES = "not_serious"
    outcome: OUTCOME_VALUES = "unknown"
    causality: CAUSALITY_VALUES = "unassessed"
    narrative: Optional[str] = None

    # Priority 3(b) -- Safety Signal Engine inputs. All optional: recording
    # an AE/SAE never requires these, but the signal detector can only use
    # cases where drug + batch_number are both present.
    drug: Optional[str] = None
    batch_number: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    administration_date: Optional[datetime] = None
    location: Optional[str] = None

    # Priority 1(b) SIH improvements. Both optional for the same reason as
    # the block above: recording an AE/SAE never requires them.
    symptom_onset_date: Optional[datetime] = None
    action_taken: Optional[ACTION_TAKEN_VALUES] = None

    class Config:
        extra = "forbid"


class SafetyCaseStatusUpdate(BaseModel):
    status: SAFETY_STATUS_VALUES

    class Config:
        extra = "forbid"


# ---------- Priority 3(b): Safety Signal Engine ----------

SIGNAL_STATUS_VALUES = Literal["open", "under_review", "escalated", "dismissed"]


class SafetySignalDetectRequest(BaseModel):
    study_id: Optional[int] = None  # None = scan across all studies
    window_hours: float = 6.0  # rolling time window that chains events into one cluster
    min_patients: int = 2  # minimum distinct patients before a cluster is raised as a signal

    class Config:
        extra = "forbid"


class SafetySignalStatusUpdate(BaseModel):
    status: SIGNAL_STATUS_VALUES
    review_notes: Optional[str] = None

    class Config:
        extra = "forbid"
