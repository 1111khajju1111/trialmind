"""
Priority 7 -- FHIR + CDISC Demonstrator (interoperability, not certification).

Per the SIH26046 first-shot plan: "Do not attempt full standards
certification in the first shot. Build a convincing interoperability
demonstrator." This module maps real rows from the existing domain models
(Study, Site, Patient, StudySubject, SafetyCase) into FHIR R4-shaped JSON
resources and SDTM-style CSV domains, on demand, from whatever data
actually exists in the database -- not hard-coded fixtures. It intentionally
does not implement full FHIR validation, terminology binding, or the
complete SDTM/ADaM/Define-XML pipeline (see "What NOT to Implement in the
First Shot" in the plan).

Field-mapping notes (also surfaced via GET /interop/mapping):

  FHIR Patient            <- Patient (pseudonymous: FHIR id = "patient-{id}",
                             no name/address exposed, per Priority 6)
  FHIR ResearchStudy      <- Study
  FHIR ResearchSubject    <- StudySubject (links Patient <-> ResearchStudy,
                             carries consent/status)
  FHIR AdverseEvent       <- SafetyCase
  FHIR Consent            <- StudySubject.consent_* fields
  FHIR Observation        <- Patient.biomarkers (parsed key:value pairs)

  SDTM DM (Demographics)  <- StudySubject + Patient (age, condition as a
                             proxy for a diagnosis-driven field, site/arm)
  SDTM AE (Adverse Events) <- SafetyCase
"""
import csv
import io
from datetime import datetime, timezone

from app import models
from app.services.eligibility_engine import parse_biomarkers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- FHIR ----

def fhir_patient(patient: "models.Patient") -> dict:
    """Pseudonymous per Priority 6: no name/address in the exported
    resource, only a stable synthetic identifier and de-identified
    clinical attributes."""
    return {
        "resourceType": "Patient",
        "id": f"patient-{patient.id}",
        "meta": {"profile": ["http://hl7.org/fhir/StructureDefinition/Patient"]},
        "identifier": [{"system": "urn:aiia:pseudonymous-id", "value": f"PID-{patient.id:05d}"}],
        "extension": [
            {"url": "urn:aiia:demo-note", "valueString": "Synthetic/de-identified data for SIH26046 prototype."}
        ],
        "birthDate": None,  # age used instead of DOB to avoid re-identification, common CTMS pseudonymization practice
        "extension_age": patient.age,
        "_comment": "Age is exposed as an extension rather than birthDate to avoid re-identification risk.",
    }


def fhir_research_study(study: "models.Study") -> dict:
    return {
        "resourceType": "ResearchStudy",
        "id": f"study-{study.id}",
        "identifier": [{"system": "urn:aiia:study-code", "value": study.study_code}],
        "title": study.title,
        "status": {
            "planning": "active",  # FHIR ResearchStudy has no direct "planning"; mapped conservatively
            "active": "active",
            "paused": "temporarily-closed-to-accrual",
            "completed": "completed",
            "terminated": "withdrawn",
        }.get(study.status, "active"),
        "phase": {"text": study.phase} if study.phase else None,
        "principalInvestigator": {"display": study.principal_investigator} if study.principal_investigator else None,
        "enrollment": {"targetCount": study.target_enrollment},
        "period": {
            "start": study.start_date.isoformat() if study.start_date else None,
            "end": study.end_date.isoformat() if study.end_date else None,
        },
        "extension": [
            {"url": "urn:aiia:ctri-number", "valueString": study.ctri_number},
            {"url": "urn:aiia:ctri-status", "valueString": study.ctri_status},
        ],
    }


def fhir_research_subject(db, subject: "models.StudySubject") -> dict:
    site = db.query(models.Site).filter(models.Site.id == subject.site_id).first() if subject.site_id else None
    return {
        "resourceType": "ResearchSubject",
        "id": f"researchsubject-{subject.id}",
        "identifier": [{"system": "urn:aiia:subject-code", "value": subject.subject_code or f"SUBJ-{subject.id:05d}"}],
        "status": {
            "screened": "eligibility",
            "eligible": "eligibility",
            "enrolled": "on-study",
            "randomized": "on-study",
            "completed": "off-study",
            "withdrawn": "withdrawn",
        }.get(subject.status, "candidate"),
        "study": {"reference": f"ResearchStudy/study-{subject.study_id}"},
        "individual": {"reference": f"Patient/patient-{subject.patient_id}"},
        "site": {"display": site.institution} if site else None,
        "consent": {"reference": f"Consent/consent-{subject.id}"},
    }


def fhir_consent(subject: "models.StudySubject") -> dict:
    return {
        "resourceType": "Consent",
        "id": f"consent-{subject.id}",
        "status": {
            "not_obtained": "proposed",
            "obtained": "active",
            "withdrawn": "inactive",
        }.get(subject.consent_status or "not_obtained", "proposed"),
        "patient": {"reference": f"Patient/patient-{subject.patient_id}"},
        "dateTime": subject.consent_date.isoformat() if subject.consent_date else None,
        "policyText": subject.consent_version,
    }


def fhir_adverse_event(case: "models.SafetyCase") -> dict:
    return {
        "resourceType": "AdverseEvent",
        "id": f"adverseevent-{case.id}",
        "actuality": "actual",
        "event": {"text": case.event_term},
        "subject": {"reference": f"Patient/patient-{case.patient_id}"},
        "study": [{"reference": f"ResearchStudy/study-{case.study_id}"}],
        "date": case.event_date.isoformat() if case.event_date else None,
        "seriousness": {"text": case.seriousness},
        "severity": {"text": case.severity},
        "outcome": {"text": case.outcome},
        "extension": [
            {"url": "urn:aiia:causality", "valueString": case.causality},
            {"url": "urn:aiia:case-status", "valueString": case.status},
            # MedDRA/WHODrug coding not implemented in the first shot (see
            # plan section 14) -- this extension marks the gap explicitly
            # rather than silently omitting it.
            {"url": "urn:aiia:meddra-coded", "valueBoolean": False},
        ],
    }


def fhir_observations_for_patient(patient: "models.Patient") -> list[dict]:
    """One synthetic Observation per parsed biomarker -- a lightweight
    stand-in for real lab-result FHIR resources, built from the same
    biomarker string the eligibility engine already parses."""
    obs = []
    for key, value in parse_biomarkers(patient.biomarkers).items():
        obs.append({
            "resourceType": "Observation",
            "id": f"observation-{patient.id}-{key.lower()}",
            "status": "final",
            "code": {"text": key},
            "subject": {"reference": f"Patient/patient-{patient.id}"},
            "valueQuantity": {"value": value} if isinstance(value, (int, float)) else None,
            "valueString": value if isinstance(value, str) else None,
        })
    return obs


FHIR_RESOURCE_TYPES = ["Patient", "ResearchStudy", "ResearchSubject", "Observation", "AdverseEvent", "Consent"]


def build_fhir_bundle(db, resource_type: str, study_id: int | None = None) -> dict:
    """Builds a FHIR Bundle of the requested resource type from live data,
    optionally scoped to one study."""
    entries: list[dict] = []

    if resource_type == "Patient":
        q = db.query(models.Patient)
        if study_id is not None:
            patient_ids = [s.patient_id for s in db.query(models.StudySubject).filter(models.StudySubject.study_id == study_id)]
            q = q.filter(models.Patient.id.in_(patient_ids))
        entries = [fhir_patient(p) for p in q.all()]

    elif resource_type == "ResearchStudy":
        q = db.query(models.Study)
        if study_id is not None:
            q = q.filter(models.Study.id == study_id)
        entries = [fhir_research_study(s) for s in q.all()]

    elif resource_type == "ResearchSubject":
        q = db.query(models.StudySubject)
        if study_id is not None:
            q = q.filter(models.StudySubject.study_id == study_id)
        entries = [fhir_research_subject(db, s) for s in q.all()]

    elif resource_type == "Consent":
        q = db.query(models.StudySubject)
        if study_id is not None:
            q = q.filter(models.StudySubject.study_id == study_id)
        entries = [fhir_consent(s) for s in q.all()]

    elif resource_type == "AdverseEvent":
        q = db.query(models.SafetyCase)
        if study_id is not None:
            q = q.filter(models.SafetyCase.study_id == study_id)
        entries = [fhir_adverse_event(c) for c in q.all()]

    elif resource_type == "Observation":
        if study_id is not None:
            patient_ids = [s.patient_id for s in db.query(models.StudySubject).filter(models.StudySubject.study_id == study_id)]
            patients = db.query(models.Patient).filter(models.Patient.id.in_(patient_ids)).all()
        else:
            patients = db.query(models.Patient).all()
        for p in patients:
            entries.extend(fhir_observations_for_patient(p))

    else:
        return {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "diagnostics": f"Unknown resource type '{resource_type}'."}]}

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "timestamp": _now_iso(),
        "total": len(entries),
        "entry": [{"resource": e} for e in entries],
    }


# ---------------------------------------------------------------- SDTM ----

SDTM_DOMAINS = ["DM", "AE"]


def sdtm_dm_csv(db, study_id: int | None = None) -> str:
    """SDTM Demographics (DM) domain -- one row per StudySubject.
    Uses the standard SDTM DM column names where a direct mapping exists;
    AGE/SEX/RACE beyond what's collected are intentionally omitted rather
    than fabricated (see mapping doc)."""
    q = db.query(models.StudySubject)
    if study_id is not None:
        q = q.filter(models.StudySubject.study_id == study_id)
    subjects = q.all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID", "AGE", "ARMCD", "RFSTDTC", "DMDTC"])
    for s in subjects:
        study = db.query(models.Study).filter(models.Study.id == s.study_id).first()
        patient = db.query(models.Patient).filter(models.Patient.id == s.patient_id).first()
        writer.writerow([
            study.study_code if study else s.study_id,
            "DM",
            s.subject_code or f"SUBJ-{s.id:05d}",
            s.id,
            s.site_id or "",
            patient.age if patient else "",
            s.status.upper() if s.status else "",
            s.enrolled_date.date().isoformat() if s.enrolled_date else "",
            _now_iso(),
        ])
    return buf.getvalue()


def sdtm_ae_csv(db, study_id: int | None = None) -> str:
    """SDTM Adverse Events (AE) domain -- one row per SafetyCase."""
    q = db.query(models.SafetyCase)
    if study_id is not None:
        q = q.filter(models.SafetyCase.study_id == study_id)
    cases = q.all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["STUDYID", "DOMAIN", "USUBJID", "AETERM", "AESEV", "AESER", "AEOUT", "AEREL", "AESTDTC"])
    for c in cases:
        study = db.query(models.Study).filter(models.Study.id == c.study_id).first()
        writer.writerow([
            study.study_code if study else c.study_id,
            "AE",
            f"PT-{c.patient_id:05d}",
            c.event_term,
            c.severity.upper() if c.severity else "",
            "Y" if c.is_serious else "N",
            c.outcome.upper() if c.outcome else "",
            c.causality.upper() if c.causality else "",
            c.event_date.date().isoformat() if c.event_date else "",
        ])
    return buf.getvalue()


FIELD_MAPPING_DOC = """\
# SIH26046 -- Internal Data Model to FHIR R4 / CDISC SDTM Mapping

This is a demonstrator mapping (Priority 7), not a certified conformance
statement. It documents which internal fields feed which external
standard fields today.

## FHIR R4

| FHIR Resource      | Internal Source                          | Notes |
|--------------------|-------------------------------------------|-------|
| Patient             | Patient                                   | Pseudonymous: no name/address exported, per consent/data-protection MVP. |
| ResearchStudy        | Study                                     | ctri_number/ctri_status exposed as extensions (no standard FHIR element). |
| ResearchSubject      | StudySubject                              | status mapped from the internal recruitment funnel state. |
| Consent              | StudySubject.consent_status/version/date  | 1:1 with a StudySubject, not a separate table. |
| AdverseEvent         | SafetyCase                                | MedDRA/WHODrug coding NOT implemented (flagged via extension). |
| Observation          | Patient.biomarkers (parsed)               | Demonstrator only; not a real lab-result feed. |

## CDISC SDTM (demonstrator domains only: DM, AE)

| SDTM Variable | Domain | Internal Source |
|---------------|--------|------------------|
| STUDYID       | DM/AE  | Study.study_code |
| USUBJID       | DM     | StudySubject.subject_code (or synthetic SUBJ-id) |
| AGE           | DM     | Patient.age |
| ARMCD         | DM     | StudySubject.status (not a true randomization arm in this build) |
| AETERM        | AE     | SafetyCase.event_term |
| AESEV         | AE     | SafetyCase.severity |
| AESER         | AE     | SafetyCase.is_serious |
| AEOUT         | AE     | SafetyCase.outcome |
| AEREL         | AE     | SafetyCase.causality |

Full CDASH/SDTM/ADaM implementation, Define-XML generation, and MedDRA/
WHODrug terminology binding are explicitly out of scope for the first
shot (see implementation plan, "What NOT to Implement in the First Shot").
"""
