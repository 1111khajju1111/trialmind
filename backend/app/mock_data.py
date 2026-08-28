import json
from app.models import (
    Patient, Trial, LabEquipment, Sample, ProtocolChunk,
    Study, Site, StudyMilestone, ProtocolDeviation, MonitoringVisit, StudySubject,
    SafetyCase,
)
from app.services.rag_service import chunk_text
from app.services.recruitment import recompute_recruitment
from app.services.safety import compute_due_date, is_serious
from datetime import datetime, timedelta

GLYCO3_PROTOCOL_TEXT = """
GLYCO-3 Trial Protocol - Section 4: Eligibility Criteria

4.1 Inclusion Criteria
Patients must be between 40 and 65 years of age at the time of screening.
Patients must have a confirmed diagnosis of Type 2 Diabetes Mellitus.
Glycated hemoglobin (HbA1c) must be between 7.0% and 9.5% inclusive at
screening, measured by a certified laboratory. Body Mass Index (BMI) must
fall between 27 and 35 kg/m^2. Patients must not have received insulin
therapy at any point prior to enrollment, as prior insulin use may
confound the study's primary endpoint of HbA1c reduction.

4.2 Exclusion Criteria
Patients with severe renal impairment (eGFR < 30 mL/min/1.73m^2) are
excluded due to altered drug clearance. Pregnant or breastfeeding patients
are excluded. Patients with an active cardiovascular event (myocardial
infarction, unstable angina, stroke) within the 6 months prior to
screening are excluded due to safety concerns with the investigational
agent. Patients currently enrolled in another interventional trial are
excluded to avoid confounding effects.

4.3 Rationale for Age and BMI Ranges
The 40-65 age range was selected to capture the population in which
Type 2 Diabetes most commonly presents while excluding elderly patients
at higher risk of treatment-related adverse events. The BMI range of
27-35 reflects the overweight-to-moderately-obese population most
representative of the target treatment demographic for this compound.
"""

ARTHRIX_PROTOCOL_TEXT = """
ARTHRIX-1 Trial Protocol - Section 3: Eligibility Criteria

3.1 Inclusion Criteria
Patients must be between 18 and 70 years of age. Patients must be
Rheumatoid Factor (RF) positive as confirmed by serology. C-reactive
protein (CRP) must be above 10 mg/L at screening, indicating moderate to
severe disease activity consistent with the trial's target population.

3.2 Exclusion Criteria
Patients with an active infection at screening are excluded due to
immunosuppressive risk from the investigational biologic. Patients who
have received any other biologic therapy within the 3 months prior to
screening are excluded to allow adequate washout and avoid confounding
the safety and efficacy assessments.
"""

# A third trial with ONLY machine-checkable criteria (no verification-required
# items at all). This exists specifically so a clean ELIGIBLE verdict is
# reachable in the demo -- GLYCO-3 and ARTHRIX-1 both always have at least
# one verification-required criterion by design, so no patient can ever be
# a clean ELIGIBLE there. Per the review's P0 "clean ELIGIBLE patient" item.
LIPID2_PROTOCOL_TEXT = """
LIPID-2 Trial Protocol - Section 2: Eligibility Criteria

2.1 Inclusion Criteria
Patients must be between 35 and 70 years of age. Patients must have a
confirmed diagnosis of Hyperlipidemia. LDL cholesterol must be between
130 and 190 mg/dL at screening. Triglycerides must be below 400 mg/dL.

2.2 Exclusion Criteria
Patients with an eGFR below 45 mL/min/1.73m^2 are excluded due to renal
safety considerations with the investigational lipid-lowering agent.

Note: this protocol intentionally contains only objective, numerically
checkable criteria for demonstration purposes.
"""

# --- Three additional protocols uploaded as source PDFs, seeded here so the
# demo has richer, more realistic material alongside the synthetic trials
# above. Unlike LIPID-2, these mirror real trial documents in that several
# criteria are inherently qualitative (investigator judgment, informed
# consent, symptom history) and so are marked verification_required rather
# than forced into a machine-checkable rule that doesn't really fit.

ARTHRIX2_PROTOCOL_TEXT = """
ARTHRIX-2: Novel JAK Inhibitor in Moderate-to-Severe Rheumatoid Arthritis
Protocol ID: ARTHRIX-2 | Condition: Rheumatoid Arthritis

4.1 Inclusion Criteria
Subjects must meet all of the following criteria to be eligible for enrollment:
- Age 18 years or older.
- Diagnosis of rheumatoid arthritis according to ACR/EULAR 2010 criteria for >= 6 months.
- Active disease defined as DAS28-CRP >= 3.2 at screening.
- Inadequate response to at least one conventional synthetic DMARD (e.g., methotrexate).
- RF positive or anti-CCP positive (seropositive RA).

4.2 Exclusion Criteria
Subjects who meet any of the following criteria will be excluded from the study:
- Current or prior use of any JAK inhibitor.
- Active or latent tuberculosis (positive QuantiFERON or abnormal chest X-ray).
- History of lymphoproliferative disease or malignancy within the past 5 years (except
  successfully treated non-melanoma skin cancer).
- Severe hepatic impairment (Child-Pugh Class C).
- Absolute neutrophil count < 1.0 x 10^9/L or lymphocyte count < 0.5 x 10^9/L.
- Pregnant, breastfeeding, or unwilling to use highly effective contraception.
- Any clinically significant infection requiring systemic antibiotics within 4 weeks of screening.

4.3 Additional Notes
Several criteria (active TB screening, malignancy history, clinically significant infection)
require source-document verification and cannot be fully automated from structured lab data
alone.
This is a synthetic sample protocol created for demonstration purposes only. Not for clinical use.
"""

GLYCO4_PROTOCOL_TEXT = """
GLYCO-4: Once-Weekly Dual GIP/GLP-1 Receptor Agonist in Type 2 Diabetes
Protocol ID: GLYCO-4 | Condition: Type 2 Diabetes

4.1 Inclusion Criteria
Subjects must meet all of the following criteria to be eligible for enrollment:
- Age 18 to 75 years inclusive.
- Diagnosis of Type 2 Diabetes Mellitus for at least 6 months.
- HbA1c between 7.0% and 10.5% (inclusive) at screening.
- BMI >= 25 kg/m^2 and <= 45 kg/m^2.
- Stable dose of metformin (>= 1500 mg/day or maximum tolerated dose) for >= 8 weeks.
- eGFR >= 45 mL/min/1.73 m^2.

4.2 Exclusion Criteria
Subjects who meet any of the following criteria will be excluded from the study:
- Type 1 diabetes or secondary forms of diabetes.
- History of pancreatitis or pancreatic cancer.
- Severe diabetic retinopathy or maculopathy requiring active treatment.
- Uncontrolled hypertension (BP > 160/100 mmHg).
- Significant cardiovascular disease (NYHA Class III-IV heart failure, recent MI < 3 months).
- Pregnant or planning pregnancy during the study period.
- Any condition that, in the opinion of the investigator, would interfere with study
  participation or safety.

4.3 Additional Notes
The final exclusion criterion regarding investigator judgment is qualitative and will require
manual verification by the clinical coordinator. All other criteria are intended to be
machine-checkable.
This is a synthetic sample protocol created for demonstration purposes only. Not for clinical use.
"""

LIPID3_PROTOCOL_TEXT = """
LIPID-3: Efficacy of Novel PCSK9 Inhibitor in Hyperlipidemia
Protocol ID: LIPID-3 | Condition: Hyperlipidemia

4.1 Inclusion Criteria
Subjects must meet all of the following criteria to be eligible for enrollment:
- Age between 40 and 75 years (inclusive) at the time of screening.
- Documented diagnosis of primary hyperlipidemia or mixed dyslipidemia.
- LDL-C >= 100 mg/dL (2.6 mmol/L) despite stable statin therapy for >= 4 weeks.
- BMI between 18.5 and 35 kg/m^2.
- Willing and able to provide written informed consent.

4.2 Exclusion Criteria
Subjects who meet any of the following criteria will be excluded from the study:
- History of myocardial infarction, stroke, or coronary revascularization within the past
  6 months.
- Uncontrolled hypertension (systolic BP > 160 mmHg or diastolic BP > 100 mmHg).
- Active liver disease or ALT/AST > 3x upper limit of normal.
- eGFR < 30 mL/min/1.73 m^2 (severe renal impairment).
- Known hypersensitivity to any component of the investigational product.
- Pregnancy or breastfeeding.

4.3 Additional Notes
All laboratory values must be obtained within 14 days of the screening visit. Subjects
currently participating in another interventional trial are not eligible.
This is a synthetic sample protocol created for demonstration purposes only. Not for clinical use.
"""


def seed_if_empty(db):
    if db.query(Patient).count() == 0:
        patients = [
            # Clean candidate: age/HbA1c/BMI/eGFR all pass -> POTENTIAL_MATCH
            # (two criteria, prior insulin + recent CV event, always require
            # human verification by design -- see structured criteria below)
            Patient(name="J. Alvarez", age=54, condition="Type 2 Diabetes",
                    biomarkers="HbA1c:7.8,BMI:29,eGFR:75", location="Austin, TX"),
            # HbA1c out of range, eGFR provided so the failure is isolated
            # and not confounded with a missing-data signal -> NOT_ELIGIBLE
            Patient(name="M. Chen", age=61, condition="Type 2 Diabetes",
                    biomarkers="HbA1c:10.2,BMI:31,eGFR:60", location="San Jose, CA"),
            # Age out of range, eGFR provided -> NOT_ELIGIBLE (isolated failure)
            Patient(name="R. Patel", age=71, condition="Type 2 Diabetes",
                    biomarkers="HbA1c:7.5,BMI:28,eGFR:60", location="Chicago, IL"),
            Patient(name="S. Okafor", age=39, condition="Rheumatoid Arthritis",
                    biomarkers="CRP:12.1,RF:positive", location="Atlanta, GA"),
            # The deliberate "difficult verification case" from the review:
            # age/HbA1c/BMI all pass, but eGFR is missing (not zero, not
            # provided) -> should NOT be a clean ELIGIBLE, must surface as
            # POTENTIAL_MATCH / VERIFICATION_REQUIRED
            Patient(name="L. Kim", age=58, condition="Type 2 Diabetes",
                    biomarkers="HbA1c:8.4,BMI:33", location="Seattle, WA"),
            # Clean ELIGIBLE demo patient for LIPID-2: every criterion in
            # that trial is machine-checkable and this patient passes all of
            # them with data provided, so the agent should return a genuine
            # ELIGIBLE verdict (not just a high score).
            Patient(name="A. Torres", age=52, condition="Hyperlipidemia",
                    biomarkers="LDL:165,Triglycerides:210,eGFR:88", location="Denver, CO"),
            # Demo patient for ARTHRIX-2: has the newer biomarker fields that
            # protocol references (DAS28-CRP, ANC, lymphocyte count) so its
            # machine-checkable criteria have data to evaluate against --
            # several qualitative items (TB screening, malignancy history,
            # DMARD response) still land as verification_required by design,
            # matching what the real protocol itself calls out as
            # non-automatable.
            Patient(name="T. Nakamura", age=45, condition="Rheumatoid Arthritis",
                    biomarkers="DAS28_CRP:4.1,RF:positive,ANC:2.5,Lymphocytes:1.2",
                    location="Portland, OR"),
            # Demo patient for LIPID-3: has BMI on file (A. Torres above does
            # not), so LIPID-3's BMI criterion has something to check.
            Patient(name="E. Whitfield", age=58, condition="Hyperlipidemia",
                    biomarkers="LDL:145,BMI:27,Triglycerides:180,eGFR:75",
                    location="Nashville, TN"),
        ]
        db.add_all(patients)

    if db.query(Trial).count() == 0:
        glyco3_criteria = json.dumps([
            {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
             "operator": "between", "value": [40, 65], "unit": "years",
             "source_text": "Patients must be between 40 and 65 years of age at the time of screening.",
             "verification_required": False},
            {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
             "operator": "equals", "value": "Type 2 Diabetes", "unit": "",
             "source_text": "Patients must have a confirmed diagnosis of Type 2 Diabetes Mellitus.",
             "verification_required": False},
            {"criterion_id": "hba1c_range", "type": "inclusion", "field": "HbA1c", "label": "HbA1c",
             "operator": "between", "value": [7.0, 9.5], "unit": "%",
             "source_text": "Glycated hemoglobin (HbA1c) must be between 7.0% and 9.5% inclusive at screening.",
             "verification_required": False},
            {"criterion_id": "bmi_range", "type": "inclusion", "field": "BMI", "label": "BMI",
             "operator": "between", "value": [27, 35], "unit": "kg/m^2",
             "source_text": "Body Mass Index (BMI) must fall between 27 and 35 kg/m^2.",
             "verification_required": False},
            {"criterion_id": "no_prior_insulin", "type": "inclusion", "field": "prior_insulin_use",
             "label": "No prior insulin therapy", "operator": None, "value": None, "unit": "",
             "source_text": "Patients must not have received insulin therapy at any point prior to enrollment.",
             "verification_required": True},
            {"criterion_id": "renal_function", "type": "exclusion", "field": "eGFR",
             "label": "Renal function (eGFR)", "operator": "gte", "value": 30, "unit": "mL/min/1.73m^2",
             "source_text": "Patients with severe renal impairment (eGFR < 30) are excluded.",
             "verification_required": False},
            {"criterion_id": "cv_event", "type": "exclusion", "field": "recent_cv_event",
             "label": "No recent cardiovascular event", "operator": None, "value": None, "unit": "",
             "source_text": "Patients with an active cardiovascular event within 6 months prior to "
                             "screening are excluded.",
             "verification_required": True},
        ])
        arthrix_criteria = json.dumps([
            {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
             "operator": "between", "value": [18, 70], "unit": "years",
             "source_text": "Patients must be between 18 and 70 years of age.",
             "verification_required": False},
            {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
             "operator": "equals", "value": "Rheumatoid Arthritis", "unit": "",
             "source_text": "Diagnosis of Rheumatoid Arthritis required for enrollment.",
             "verification_required": False},
            {"criterion_id": "crp_threshold", "type": "inclusion", "field": "CRP", "label": "CRP",
             "operator": "gte", "value": 10, "unit": "mg/L",
             "source_text": "C-reactive protein (CRP) must be above 10 mg/L at screening.",
             "verification_required": False},
            {"criterion_id": "active_infection", "type": "exclusion", "field": "active_infection",
             "label": "No active infection", "operator": None, "value": None, "unit": "",
             "source_text": "Patients with an active infection at screening are excluded.",
             "verification_required": True},
        ])

        arthrix2_criteria = json.dumps([
            {"criterion_id": "age_min", "type": "inclusion", "field": "age", "label": "Age",
             "operator": "gte", "value": 18, "unit": "years",
             "source_text": "Age 18 years or older.",
             "verification_required": False},
            {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
             "operator": "equals", "value": "Rheumatoid Arthritis", "unit": "",
             "source_text": "Diagnosis of rheumatoid arthritis according to ACR/EULAR 2010 criteria "
                             "for >= 6 months.",
             "verification_required": False},
            {"criterion_id": "das28_crp", "type": "inclusion", "field": "DAS28_CRP", "label": "DAS28-CRP",
             "operator": "gte", "value": 3.2, "unit": "",
             "source_text": "Active disease defined as DAS28-CRP >= 3.2 at screening.",
             "verification_required": False},
            {"criterion_id": "dmard_response", "type": "inclusion", "field": "dmard_response",
             "label": "Inadequate response to a conventional DMARD", "operator": None, "value": None, "unit": "",
             "source_text": "Inadequate response to at least one conventional synthetic DMARD "
                             "(e.g., methotrexate).",
             "verification_required": True},
            {"criterion_id": "seropositive", "type": "inclusion", "field": "RF",
             "label": "Seropositivity (RF or anti-CCP)", "operator": None, "value": None, "unit": "",
             "source_text": "RF positive or anti-CCP positive (seropositive RA). Two possible "
                             "pathways to seropositivity -- reviewed manually rather than checking "
                             "RF alone, since a patient positive only for anti-CCP would otherwise "
                             "be missed.",
             "verification_required": True},
            {"criterion_id": "jak_inhibitor_use", "type": "exclusion", "field": "jak_inhibitor_use",
             "label": "No current/prior JAK inhibitor use", "operator": None, "value": None, "unit": "",
             "source_text": "Current or prior use of any JAK inhibitor.",
             "verification_required": True},
            {"criterion_id": "tuberculosis", "type": "exclusion", "field": "tuberculosis",
             "label": "No active/latent tuberculosis", "operator": None, "value": None, "unit": "",
             "source_text": "Active or latent tuberculosis (positive QuantiFERON or abnormal chest X-ray).",
             "verification_required": True},
            {"criterion_id": "malignancy_history", "type": "exclusion", "field": "malignancy_history",
             "label": "No malignancy/lymphoproliferative disease history", "operator": None, "value": None,
             "unit": "",
             "source_text": "History of lymphoproliferative disease or malignancy within the past "
                             "5 years (except successfully treated non-melanoma skin cancer).",
             "verification_required": True},
            {"criterion_id": "hepatic_impairment", "type": "exclusion", "field": "hepatic_impairment",
             "label": "No severe hepatic impairment", "operator": None, "value": None, "unit": "",
             "source_text": "Severe hepatic impairment (Child-Pugh Class C).",
             "verification_required": True},
            {"criterion_id": "anc_min", "type": "exclusion", "field": "ANC", "label": "Absolute neutrophil count",
             "operator": "gte", "value": 1.0, "unit": "x10^9/L",
             "source_text": "Absolute neutrophil count < 1.0 x 10^9/L excludes.",
             "verification_required": False},
            {"criterion_id": "lymphocyte_min", "type": "exclusion", "field": "Lymphocytes",
             "label": "Lymphocyte count", "operator": "gte", "value": 0.5, "unit": "x10^9/L",
             "source_text": "Lymphocyte count < 0.5 x 10^9/L excludes.",
             "verification_required": False},
            {"criterion_id": "pregnancy", "type": "exclusion", "field": "pregnancy",
             "label": "Not pregnant/breastfeeding", "operator": None, "value": None, "unit": "",
             "source_text": "Pregnant, breastfeeding, or unwilling to use highly effective contraception.",
             "verification_required": True},
            {"criterion_id": "significant_infection", "type": "exclusion", "field": "significant_infection",
             "label": "No clinically significant recent infection", "operator": None, "value": None, "unit": "",
             "source_text": "Any clinically significant infection requiring systemic antibiotics "
                             "within 4 weeks of screening.",
             "verification_required": True},
        ])

        glyco4_criteria = json.dumps([
            {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
             "operator": "between", "value": [18, 75], "unit": "years",
             "source_text": "Age 18 to 75 years inclusive.",
             "verification_required": False},
            {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
             "operator": "equals", "value": "Type 2 Diabetes", "unit": "",
             "source_text": "Diagnosis of Type 2 Diabetes Mellitus for at least 6 months.",
             "verification_required": False},
            {"criterion_id": "hba1c_range", "type": "inclusion", "field": "HbA1c", "label": "HbA1c",
             "operator": "between", "value": [7.0, 10.5], "unit": "%",
             "source_text": "HbA1c between 7.0% and 10.5% (inclusive) at screening.",
             "verification_required": False},
            {"criterion_id": "bmi_range", "type": "inclusion", "field": "BMI", "label": "BMI",
             "operator": "between", "value": [25, 45], "unit": "kg/m^2",
             "source_text": "BMI >= 25 kg/m^2 and <= 45 kg/m^2.",
             "verification_required": False},
            {"criterion_id": "metformin_stable", "type": "inclusion", "field": "metformin_stable",
             "label": "Stable metformin dose >= 8 weeks", "operator": None, "value": None, "unit": "",
             "source_text": "Stable dose of metformin (>= 1500 mg/day or maximum tolerated dose) "
                             "for >= 8 weeks.",
             "verification_required": True},
            {"criterion_id": "egfr_min", "type": "inclusion", "field": "eGFR", "label": "Renal function (eGFR)",
             "operator": "gte", "value": 45, "unit": "mL/min/1.73m^2",
             "source_text": "eGFR >= 45 mL/min/1.73 m^2.",
             "verification_required": False},
            {"criterion_id": "diabetes_type", "type": "exclusion", "field": "diabetes_type",
             "label": "Not Type 1 or secondary diabetes", "operator": None, "value": None, "unit": "",
             "source_text": "Type 1 diabetes or secondary forms of diabetes.",
             "verification_required": True},
            {"criterion_id": "pancreatitis_history", "type": "exclusion", "field": "pancreatitis_history",
             "label": "No pancreatitis/pancreatic cancer history", "operator": None, "value": None, "unit": "",
             "source_text": "History of pancreatitis or pancreatic cancer.",
             "verification_required": True},
            {"criterion_id": "retinopathy", "type": "exclusion", "field": "retinopathy",
             "label": "No severe diabetic retinopathy/maculopathy", "operator": None, "value": None, "unit": "",
             "source_text": "Severe diabetic retinopathy or maculopathy requiring active treatment.",
             "verification_required": True},
            {"criterion_id": "hypertension", "type": "exclusion", "field": "hypertension",
             "label": "Blood pressure controlled", "operator": None, "value": None, "unit": "",
             "source_text": "Uncontrolled hypertension (BP > 160/100 mmHg).",
             "verification_required": True},
            {"criterion_id": "cardiovascular_disease", "type": "exclusion", "field": "cardiovascular_disease",
             "label": "No significant cardiovascular disease", "operator": None, "value": None, "unit": "",
             "source_text": "Significant cardiovascular disease (NYHA Class III-IV heart failure, "
                             "recent MI < 3 months).",
             "verification_required": True},
            {"criterion_id": "pregnancy", "type": "exclusion", "field": "pregnancy",
             "label": "Not pregnant/planning pregnancy", "operator": None, "value": None, "unit": "",
             "source_text": "Pregnant or planning pregnancy during the study period.",
             "verification_required": True},
            {"criterion_id": "investigator_judgment", "type": "exclusion", "field": "investigator_judgment",
             "label": "No investigator safety/participation concern", "operator": None, "value": None, "unit": "",
             "source_text": "Any condition that, in the opinion of the investigator, would interfere "
                             "with study participation or safety.",
             "verification_required": True},
        ])

        lipid3_criteria = json.dumps([
            {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
             "operator": "between", "value": [40, 75], "unit": "years",
             "source_text": "Age between 40 and 75 years (inclusive) at the time of screening.",
             "verification_required": False},
            {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
             "operator": "equals", "value": "Hyperlipidemia", "unit": "",
             "source_text": "Documented diagnosis of primary hyperlipidemia or mixed dyslipidemia.",
             "verification_required": False},
            {"criterion_id": "ldl_min", "type": "inclusion", "field": "LDL", "label": "LDL cholesterol",
             "operator": "gte", "value": 100, "unit": "mg/dL",
             "source_text": "LDL-C >= 100 mg/dL (2.6 mmol/L) despite stable statin therapy for >= 4 weeks.",
             "verification_required": False},
            {"criterion_id": "bmi_range", "type": "inclusion", "field": "BMI", "label": "BMI",
             "operator": "between", "value": [18.5, 35], "unit": "kg/m^2",
             "source_text": "BMI between 18.5 and 35 kg/m^2.",
             "verification_required": False},
            {"criterion_id": "informed_consent", "type": "inclusion", "field": "informed_consent",
             "label": "Able to provide informed consent", "operator": None, "value": None, "unit": "",
             "source_text": "Willing and able to provide written informed consent.",
             "verification_required": True},
            {"criterion_id": "recent_cv_event", "type": "exclusion", "field": "recent_cv_event",
             "label": "No recent MI/stroke/revascularization", "operator": None, "value": None, "unit": "",
             "source_text": "History of myocardial infarction, stroke, or coronary revascularization "
                             "within the past 6 months.",
             "verification_required": True},
            {"criterion_id": "hypertension", "type": "exclusion", "field": "hypertension",
             "label": "Blood pressure controlled", "operator": None, "value": None, "unit": "",
             "source_text": "Uncontrolled hypertension (systolic BP > 160 mmHg or diastolic BP > 100 mmHg).",
             "verification_required": True},
            {"criterion_id": "liver_disease", "type": "exclusion", "field": "liver_disease",
             "label": "No active liver disease / elevated ALT-AST", "operator": None, "value": None, "unit": "",
             "source_text": "Active liver disease or ALT/AST > 3x upper limit of normal.",
             "verification_required": True},
            {"criterion_id": "renal_function", "type": "exclusion", "field": "eGFR",
             "label": "Renal function (eGFR)", "operator": "gte", "value": 30, "unit": "mL/min/1.73m^2",
             "source_text": "eGFR < 30 mL/min/1.73 m^2 (severe renal impairment) excludes.",
             "verification_required": False},
            {"criterion_id": "hypersensitivity", "type": "exclusion", "field": "hypersensitivity",
             "label": "No known hypersensitivity to product", "operator": None, "value": None, "unit": "",
             "source_text": "Known hypersensitivity to any component of the investigational product.",
             "verification_required": True},
            {"criterion_id": "pregnancy", "type": "exclusion", "field": "pregnancy",
             "label": "Not pregnant/breastfeeding", "operator": None, "value": None, "unit": "",
             "source_text": "Pregnancy or breastfeeding.",
             "verification_required": True},
        ])

        trials = [
            Trial(name="GLYCO-3 Trial", condition="Type 2 Diabetes",
                  criteria=GLYCO3_PROTOCOL_TEXT, structured_criteria=glyco3_criteria),
            Trial(name="ARTHRIX-1 Trial", condition="Rheumatoid Arthritis",
                  criteria=ARTHRIX_PROTOCOL_TEXT, structured_criteria=arthrix_criteria),
            Trial(name="LIPID-2 Trial", condition="Hyperlipidemia",
                  criteria=LIPID2_PROTOCOL_TEXT, structured_criteria=json.dumps([
                      {"criterion_id": "age_range", "type": "inclusion", "field": "age", "label": "Age",
                       "operator": "between", "value": [35, 70], "unit": "years",
                       "source_text": "Patients must be between 35 and 70 years of age.",
                       "verification_required": False},
                      {"criterion_id": "diagnosis", "type": "inclusion", "field": "condition", "label": "Diagnosis",
                       "operator": "equals", "value": "Hyperlipidemia", "unit": "",
                       "source_text": "Patients must have a confirmed diagnosis of Hyperlipidemia.",
                       "verification_required": False},
                      {"criterion_id": "ldl_range", "type": "inclusion", "field": "LDL", "label": "LDL cholesterol",
                       "operator": "between", "value": [130, 190], "unit": "mg/dL",
                       "source_text": "LDL cholesterol must be between 130 and 190 mg/dL at screening.",
                       "verification_required": False},
                      {"criterion_id": "triglycerides_max", "type": "inclusion", "field": "Triglycerides",
                       "label": "Triglycerides", "operator": "lte", "value": 400, "unit": "mg/dL",
                       "source_text": "Triglycerides must be below 400 mg/dL.",
                       "verification_required": False},
                      {"criterion_id": "renal_function", "type": "exclusion", "field": "eGFR",
                       "label": "Renal function (eGFR)", "operator": "gte", "value": 45, "unit": "mL/min/1.73m^2",
                       "source_text": "Patients with an eGFR below 45 are excluded.",
                       "verification_required": False},
                  ])),
            Trial(name="ARTHRIX-2 Trial", condition="Rheumatoid Arthritis",
                  criteria=ARTHRIX2_PROTOCOL_TEXT, structured_criteria=arthrix2_criteria),
            Trial(name="GLYCO-4 Trial", condition="Type 2 Diabetes",
                  criteria=GLYCO4_PROTOCOL_TEXT, structured_criteria=glyco4_criteria),
            Trial(name="LIPID-3 Trial", condition="Hyperlipidemia",
                  criteria=LIPID3_PROTOCOL_TEXT, structured_criteria=lipid3_criteria),
        ]
        db.add_all(trials)
        db.commit()

        for trial, text in [(trials[0], GLYCO3_PROTOCOL_TEXT), (trials[1], ARTHRIX_PROTOCOL_TEXT),
                             (trials[2], LIPID2_PROTOCOL_TEXT), (trials[3], ARTHRIX2_PROTOCOL_TEXT),
                             (trials[4], GLYCO4_PROTOCOL_TEXT), (trials[5], LIPID3_PROTOCOL_TEXT)]:
            for i, chunk in enumerate(chunk_text(text, chunk_size=80, overlap=15)):
                db.add(ProtocolChunk(trial_id=trial.id, chunk_index=i, content=chunk))
        db.commit()

        # Seed one demo Study (Priority 1 CTMS) linked to the GLYCO-3 trial,
        # with two sites, a mix of milestone states, one open deviation and
        # one monitoring visit -- gives the end-to-end demo scenario
        # (Section 16 of the implementation plan) a study to walk through
        # immediately, without requiring manual setup first.
        if db.query(Study).count() == 0:
            glyco3_trial = trials[0]
            study = Study(
                study_code="STUDY-001",
                title="GLYCO-3: Once-Daily Oral Agent in Type 2 Diabetes",
                phase="Phase III",
                intervention="Investigational oral antidiabetic agent",
                principal_investigator="Dr. A. Rao",
                target_enrollment=150,
                start_date=datetime.utcnow() - timedelta(days=120),
                status="active",
                # Priority 4: CTRI registration fields, kept in sync with
                # the "ctri_registration" StudyMilestone below.
                ctri_number="CTRI/2025/09/078123",
                ctri_status="registered",
                ctri_registration_date=datetime.utcnow() - timedelta(days=110),
                # screened/eligible/enrolled/... counters are left at their
                # model defaults (0) here and derived below from the actual
                # StudySubject rows once they're created, via
                # recompute_recruitment() -- not hardcoded.
            )
            db.add(study)
            db.commit()
            db.refresh(study)

            glyco3_trial.study_id = study.id

            site_a = Site(
                study_id=study.id, site_code="SITE-01",
                institution="Ridgeview Metropolitan Hospital",
                pi_name="Dr. A. Rao", coordinator_name="N. Fernandes",
                activation_status="activated", enrollment_target=80,
                activated_date=datetime.utcnow() - timedelta(days=100),
            )
            site_b = Site(
                study_id=study.id, site_code="SITE-02",
                institution="Lakeside Clinical Research Center",
                pi_name="Dr. K. Mehta", coordinator_name="S. Iyer",
                activation_status="activated", enrollment_target=70,
                activated_date=datetime.utcnow() - timedelta(days=85),
            )
            db.add_all([site_a, site_b])
            db.commit()
            db.refresh(site_a)
            db.refresh(site_b)

            db.add_all([
                StudyMilestone(study_id=study.id, milestone_type="iec_submission",
                                name="IEC Submission", status="completed",
                                planned_date=datetime.utcnow() - timedelta(days=140),
                                actual_date=datetime.utcnow() - timedelta(days=138)),
                StudyMilestone(study_id=study.id, milestone_type="iec_approval",
                                name="IEC Approval", status="completed",
                                planned_date=datetime.utcnow() - timedelta(days=130),
                                actual_date=datetime.utcnow() - timedelta(days=125)),
                StudyMilestone(study_id=study.id, milestone_type="ctri_registration",
                                name="CTRI Registration (CTRI/2025/09/078123)", status="completed",
                                planned_date=datetime.utcnow() - timedelta(days=115),
                                actual_date=datetime.utcnow() - timedelta(days=110)),
                StudyMilestone(study_id=study.id, milestone_type="site_activation",
                                name="Site Activation", status="completed",
                                planned_date=datetime.utcnow() - timedelta(days=100),
                                actual_date=datetime.utcnow() - timedelta(days=100)),
                StudyMilestone(study_id=study.id, milestone_type="first_patient_in",
                                name="First Patient In", status="completed",
                                planned_date=datetime.utcnow() - timedelta(days=90),
                                actual_date=datetime.utcnow() - timedelta(days=88)),
                # Deliberately overdue -- planned in the past, no actual_date,
                # so it should surface via the compliance/dashboard alerting.
                StudyMilestone(study_id=study.id, milestone_type="close_out",
                                name="Interim Safety Review", status="pending",
                                planned_date=datetime.utcnow() - timedelta(days=5)),
                # Deliberately due-soon (Priority 4 tri-state) -- a protocol
                # amendment planned within the 14-day due-soon window.
                StudyMilestone(study_id=study.id, milestone_type="amendment",
                                name="Protocol Amendment 1 (dosing schedule clarification)",
                                status="pending",
                                planned_date=datetime.utcnow() + timedelta(days=8)),
                # CTRI update, not yet due -- on_track.
                StudyMilestone(study_id=study.id, milestone_type="ctri_update",
                                name="CTRI Update -- enrollment target revision",
                                status="pending",
                                planned_date=datetime.utcnow() + timedelta(days=45)),
                # Upcoming, not yet due.
                StudyMilestone(study_id=study.id, milestone_type="last_patient_in",
                                name="Last Patient In (target)", status="pending",
                                planned_date=datetime.utcnow() + timedelta(days=60)),
            ])

            db.add(ProtocolDeviation(
                study_id=study.id, site_id=site_a.id,
                description="Subject's Visit 3 labs drawn 2 days outside the protocol window.",
                severity="minor", resolution_status="open",
                deviation_date=datetime.utcnow() - timedelta(days=10),
            ))

            db.add(MonitoringVisit(
                study_id=study.id, site_id=site_b.id,
                visit_date=datetime.utcnow() - timedelta(days=45),
                findings="No critical findings. Minor source-document discrepancies noted and resolved.",
                overdue=False,
            ))
            db.commit()

            # Patient -> StudySubject -> Site: run every seeded patient
            # through this study's recruitment funnel at varying stages, so
            # the funnel counters are real and the demo has something to
            # click through immediately (screening -> eligibility ->
            # enrollment -> randomization -> completion, plus one
            # withdrawal). Looked up by name rather than list index so this
            # stays correct if the patient list above changes.
            def _patient(name):
                return db.query(Patient).filter(Patient.name == name).first()

            subject_plan = [
                # (patient name, site, status, notes, consent_status)
                ("J. Alvarez", site_a, "completed", "Completed all study visits per protocol.", "obtained"),
                ("M. Chen", site_a, "randomized", "Randomized to treatment arm.", "obtained"),
                ("L. Kim", site_b, "enrolled", "Enrolled; eGFR verification completed manually.", "obtained"),
                ("S. Okafor", site_b, "eligible", "Passed screening; enrollment visit pending.", "obtained"),
                ("R. Patel", site_a, "screened", "Screened; age outside inclusion range (71).", "not_obtained"),
                ("A. Torres", site_a, "screened", "Screened for general recruitment pool.", "not_obtained"),
                ("T. Nakamura", site_b, "withdrawn", "Withdrew consent after Visit 1.", "withdrawn"),
                ("E. Whitfield", site_b, "screened", "Screened; condition does not match this protocol.", "not_obtained"),
            ]
            for name, site, status, notes, consent_status in subject_plan:
                patient = _patient(name)
                if patient is None:
                    continue
                db.add(StudySubject(
                    study_id=study.id, site_id=site.id, patient_id=patient.id,
                    status=status, notes=notes,
                    enrolled_date=(datetime.utcnow() - timedelta(days=80))
                        if status in ("enrolled", "randomized", "completed") else None,
                    consent_status=consent_status,
                    consent_version="AIIA-ICF-v1.2" if consent_status != "not_obtained" else None,
                    consent_date=(datetime.utcnow() - timedelta(days=85)) if consent_status != "not_obtained" else None,
                ))
            db.commit()
            recompute_recruitment(db, study.id)
            db.commit()

            # Priority 3: seed a small, deliberately mixed set of AE/SAE
            # cases against this study so the safety dashboard and the
            # deadline engine (overdue / approaching-due) have something
            # real to show immediately after a fresh reset -- one fatal SAE
            # already overdue, one non-fatal SAE nearing its due date, a
            # closed/reported case, and a routine non-serious AE.
            def _safety_case(patient_name, site, event_term, days_ago, severity, seriousness, outcome, causality, status, narrative):
                patient = _patient(patient_name)
                if patient is None:
                    return
                event_date = datetime.utcnow() - timedelta(days=days_ago)
                due = compute_due_date(event_date, seriousness)
                reported_date = due - timedelta(hours=6) if status in ("reported", "closed") else None
                db.add(SafetyCase(
                    study_id=study.id, site_id=site.id if site else None, patient_id=patient.id,
                    event_term=event_term, event_date=event_date,
                    is_serious=is_serious(seriousness), severity=severity, seriousness=seriousness,
                    outcome=outcome, causality=causality, status=status, narrative=narrative,
                    report_due_date=due, reported_date=reported_date,
                ))

            _safety_case(
                "M. Chen", site_a, "Severe hypoglycemia requiring hospital admission", 9,
                "severe", "hospitalization", "recovered", "probable", "under_review",
                "Subject admitted overnight for symptomatic hypoglycemia; investigator assessed as "
                "probably related to study drug. Report drafted, pending PI countersignature.",
            )
            _safety_case(
                "L. Kim", site_b, "Anaphylactic reaction, ICU admission", 2,
                "severe", "life_threatening", "recovering", "definite", "draft",
                "Life-threatening reaction shortly after dosing; subject stabilized in ICU. "
                "Expedited report drafted, awaiting submission -- due within 24h of onset.",
            )
            _safety_case(
                "S. Okafor", site_b, "Mild nausea after dosing", 20,
                "mild", "not_serious", "recovered", "possible", "reported",
                "Self-limited nausea, resolved without intervention. Routine periodic report filed.",
            )
            _safety_case(
                "T. Nakamura", site_a, "Moderate rash, resolved with antihistamine", 60,
                "moderate", "not_serious", "recovered", "unlikely", "closed",
                "Localized rash, resolved with oral antihistamine. Case closed after follow-up.",
            )
            db.commit()

    if db.query(LabEquipment).count() == 0:
        equipment = [
            LabEquipment(name="Sequencer A1", equipment_type="Sequencer", status="available"),
            LabEquipment(name="Mass Spec B2", equipment_type="Mass Spectrometer", status="available"),
            LabEquipment(name="Incubator C3", equipment_type="Incubator", status="booked"),
        ]
        db.add_all(equipment)
        db.commit()

    if db.query(Sample).count() == 0:
        eq = db.query(LabEquipment).all()
        samples = [
            Sample(label="SMP-001", priority="urgent", storage_temp_c=-18.0, required_temp_c=-20.0,
                   equipment_id=eq[0].id if eq else None,
                   scheduled_time=datetime.utcnow() + timedelta(hours=2), breach_alert=True),
            Sample(label="SMP-002", priority="normal", storage_temp_c=4.0, required_temp_c=4.0,
                   equipment_id=eq[1].id if len(eq) > 1 else None,
                   scheduled_time=datetime.utcnow() + timedelta(hours=6), breach_alert=False),
            Sample(label="SMP-003", priority="high", storage_temp_c=-19.5, required_temp_c=-20.0,
                   equipment_id=None,
                   scheduled_time=None, breach_alert=False),
        ]
        db.add_all(samples)

    db.commit()
