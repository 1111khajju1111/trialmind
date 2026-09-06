"""Deterministic, additive synthetic portfolio data for SIH26046 development/demo.

The seed is safe to run repeatedly: it only inserts records that are missing.
It never deletes or rewrites user data. All records created here are synthetic.
"""
import json
from datetime import datetime, timedelta, timezone

from app import models
from app.services.rag_service import chunk_text
from app.services.recruitment import recompute_recruitment
from app.services.safety import compute_due_date
from app.services.safety_signals import detect_signals

LOCATIONS = ["New Delhi", "Hyderabad", "Vijayawada", "Bengaluru", "Chennai", "Mumbai"]


def _patients():
    """Return a balanced synthetic pool with 5 healthy volunteers.

    The first records are deliberately varied so the deterministic matcher has
    passing, failing and missing-data examples instead of a uniformly positive
    dataset. Additional records provide realistic portfolio scale.
    """
    rows = [
        models.Patient(name="AIIA Demo HV 01", age=24, condition="Healthy Volunteer", biomarkers="BMI:22.4,eGFR:105,HbA1c:5.2,ALT:21,SBP:112,DBP:72", location="Mumbai"),
        models.Patient(name="AIIA Demo HV 02", age=31, condition="Healthy Volunteer", biomarkers="BMI:24.1,eGFR:96,HbA1c:5.5,ALT:19,SBP:118,DBP:76", location="New Delhi"),
        models.Patient(name="AIIA Demo HV 03", age=42, condition="Healthy Volunteer", biomarkers="BMI:27.8,eGFR:82,HbA1c:5.8,ALT:28,SBP:124,DBP:78", location="Hyderabad"),
        models.Patient(name="AIIA Demo HV 04", age=46, condition="Healthy Volunteer", biomarkers="BMI:23.7,eGFR:88,HbA1c:5.4,ALT:22,SBP:116,DBP:74", location="Chennai"),
        models.Patient(name="AIIA Demo HV 05", age=27, condition="Healthy Volunteer", biomarkers="BMI:31.2,eGFR:101,HbA1c:5.1,ALT:18,SBP:110,DBP:70", location="Bengaluru"),
    ]
    conditions = ["Type 2 Diabetes", "Hyperlipidemia", "Hypertension", "Rheumatoid Arthritis"]
    for i in range(1, 46):
        condition = conditions[(i - 1) % len(conditions)]
        age = 30 + ((i * 7) % 43)
        if condition == "Type 2 Diabetes":
            # Every fourth diabetes patient is a clean match for DM-101.
            hba1c = 7.4 if i % 4 == 0 else 6.2 + (i % 9) * .38
            bmi = 29 if i % 4 == 0 else 22 + (i % 15)
            egfr = 78 if i % 5 else 42
            bio = f"HbA1c:{hba1c:.2f},BMI:{bmi},eGFR:{egfr},SBP:{126 + i % 35},DBP:{78 + i % 20}"
        elif condition == "Hyperlipidemia":
            ldl = 155 if i % 4 == 1 else 108 + (i % 90)
            tg = 210 if i % 5 else 430
            bio = f"LDL:{ldl},Triglycerides:{tg},BMI:{20 + i % 16},eGFR:{76 if i % 6 else 40},SBP:{122 + i % 35},DBP:{76 + i % 22}"
        elif condition == "Hypertension":
            sbp = 145 if i % 4 == 2 else 118 + i % 50
            dbp = 88 if i % 4 == 2 else 68 + i % 35
            bio = f"SBP:{sbp},DBP:{dbp},BMI:{21 + i % 15},eGFR:{72 if i % 7 else 40},HbA1c:{5.2 + (i % 10)*.18:.2f}"
        else:
            crp = 16.0 if i % 4 == 3 else 5 + (i % 20) * .8
            anc = 1.8 if i % 6 else 0.7
            bio = f"CRP:{crp:.1f},RF:{'positive' if i % 3 else 'negative'},BMI:{20 + i % 14},eGFR:{75 if i % 8 else 42},DAS28_CRP:{3.8 if i % 4 == 3 else 2.5 + (i % 20)*.12:.2f},ANC:{anc:.2f}"
        rows.append(models.Patient(name=f"AIIA Demo Patient {i:02d}", age=age, condition=condition, biomarkers=bio, location=LOCATIONS[i % len(LOCATIONS)]))
    return rows


def _protocols():
    def rules(condition, age, field, lo, hi, extra=None):
        r = [
            {"criterion_id":"age","type":"inclusion","field":"age","label":"Age","operator":"between","value":list(age),"unit":"years","verification_required":False},
            {"criterion_id":"condition","type":"inclusion","field":"condition","label":"Diagnosis","operator":"equals","value":condition,"unit":"","verification_required":False},
            {"criterion_id":field.lower(),"type":"inclusion","field":field,"label":field,"operator":"between","value":[lo,hi],"unit":"","verification_required":False},
        ]
        if extra: r.extend(extra)
        return r
    return [
      ("AIIA-DM-101","AIIA Ayurvedic Glycemic Control Study","Type 2 Diabetes",rules("Type 2 Diabetes",(40,65),"HbA1c",7,9,[{"criterion_id":"bmi","type":"inclusion","field":"BMI","label":"BMI","operator":"between","value":[25,35],"unit":"kg/m2","verification_required":False},{"criterion_id":"egfr","type":"inclusion","field":"eGFR","label":"eGFR","operator":"gte","value":45,"unit":"mL/min/1.73m2","verification_required":False}]),"Phase II",150),
      ("AIIA-DM-102","Ayurveda Metabolic Maintenance Study","Type 2 Diabetes",rules("Type 2 Diabetes",(35,70),"HbA1c",6.8,9.5,[{"criterion_id":"egfr","type":"inclusion","field":"eGFR","label":"eGFR","operator":"gte","value":45,"unit":"mL/min/1.73m2","verification_required":False}]),"Phase III",220),
      ("AIIA-LIP-103","Ayurvedic Lipid Balance Study","Hyperlipidemia",rules("Hyperlipidemia",(40,75),"LDL",130,190,[{"criterion_id":"tg","type":"inclusion","field":"Triglycerides","label":"Triglycerides","operator":"lte","value":400,"unit":"mg/dL","verification_required":False}]),"Phase II",120),
      ("AIIA-LIP-104","Preventive Dyslipidemia Study","Hyperlipidemia",rules("Hyperlipidemia",(35,70),"LDL",120,180,[{"criterion_id":"egfr","type":"inclusion","field":"eGFR","label":"eGFR","operator":"gte","value":45,"unit":"mL/min/1.73m2","verification_required":False}]),"Phase III",180),
      ("AIIA-HTN-105","Ayurvedic Blood Pressure Study","Hypertension",rules("Hypertension",(35,70),"SBP",130,160,[{"criterion_id":"dbp","type":"inclusion","field":"DBP","label":"DBP","operator":"between","value":[80,100],"unit":"mmHg","verification_required":False},{"criterion_id":"egfr","type":"inclusion","field":"eGFR","label":"eGFR","operator":"gte","value":45,"unit":"mL/min/1.73m2","verification_required":False}]),"Phase II",100),
      ("AIIA-RA-106","Ayurvedic Arthritis Activity Study","Rheumatoid Arthritis",rules("Rheumatoid Arthritis",(18,70),"CRP",10,100,[{"criterion_id":"das28","type":"inclusion","field":"DAS28_CRP","label":"DAS28-CRP","operator":"gte","value":3.2,"unit":"","verification_required":False}]),"Phase II",90),
      # For an exclusion rule, the engine interprets a failed safety-threshold
      # check as the exclusion being triggered. Therefore ANC >= 1.0 is the
      # machine-checkable safe condition; ANC < 1.0 becomes NOT_ELIGIBLE.
      ("AIIA-RA-107","Inflammatory Arthritis Longitudinal Study","Rheumatoid Arthritis",rules("Rheumatoid Arthritis",(21,75),"CRP",8,100,[{"criterion_id":"anc","type":"exclusion","field":"ANC","label":"ANC ≥ 1.0 safety threshold","operator":"gte","value":1.0,"unit":"x10^9/L","verification_required":False}]),"Phase III",140),
      ("AIIA-MET-108","Ayurvedic Metabolic Wellness Study","Type 2 Diabetes",rules("Type 2 Diabetes",(30,65),"HbA1c",6.5,8.5,[{"criterion_id":"bmi","type":"inclusion","field":"BMI","label":"BMI","operator":"between","value":[23,32],"unit":"kg/m2","verification_required":False}]),"Phase II",110),
      ("AIIA-LIP-109","Integrated Cardiometabolic Risk Study","Hyperlipidemia",rules("Hyperlipidemia",(45,75),"LDL",140,200,[{"criterion_id":"tg","type":"inclusion","field":"Triglycerides","label":"Triglycerides","operator":"lte","value":350,"unit":"mg/dL","verification_required":False}]),"Phase II",130),
      ("AIIA-HV-110","Ayurveda Healthy Volunteer Study","Healthy Volunteer",rules("Healthy Volunteer",(18,45),"BMI",18.5,29.9,[{"criterion_id":"egfr","type":"inclusion","field":"eGFR","label":"eGFR","operator":"gte","value":60,"unit":"mL/min/1.73m2","verification_required":False},{"criterion_id":"hba1c","type":"inclusion","field":"HbA1c","label":"HbA1c","operator":"between","value":[4.5,5.9],"unit":"%","verification_required":False},{"criterion_id":"alt","type":"inclusion","field":"ALT","label":"ALT","operator":"lte","value":40,"unit":"U/L","verification_required":False}]),"Phase I",60),
    ]


def seed_demo_enrichment(db):
    # Ensure at least 50 total patient records without deleting existing data.
    existing = {p.name for p in db.query(models.Patient).all()}
    pool = [p for p in _patients() if p.name not in existing]
    current_count = len(existing)
    needed = max(0, 50 - current_count)
    if needed:
        db.add_all(pool[:needed])
        db.commit()
    all_patients = db.query(models.Patient).all()

    existing_trials = {t.name: t for t in db.query(models.Trial).all()}
    new_trials = []
    for code, name, condition, criteria, phase, target in _protocols():
        if name in existing_trials:
            continue
        text = f"{name}\nProtocol ID: {code}\nCondition: {condition}\nPhase: {phase}\nTarget sample size: {target}\n\nEligibility criteria:\n" + "\n".join(f"- {x.get('label')}: {x.get('value')}" for x in criteria)
        tr = models.Trial(name=name, condition=condition, criteria=text, structured_criteria=json.dumps(criteria))
        db.add(tr); db.flush(); new_trials.append(tr)
        for idx, chunk in enumerate(chunk_text(text)):
            db.add(models.ProtocolChunk(trial_id=tr.id, chunk_index=idx, content=chunk))
    db.commit()

    study_defs = [
      ("AIIA-CTMS-001","AIIA Glycemic Control Network","Phase II","Ayurvedic intervention","Dr. Ananya Rao",150,"Type 2 Diabetes"),
      ("AIIA-CTMS-002","AIIA Lipid Balance Programme","Phase II","Ayurvedic intervention","Dr. Vivek Sharma",120,"Hyperlipidemia"),
      ("AIIA-CTMS-003","AIIA Hypertension Research Study","Phase II","Ayurvedic intervention","Dr. Meera Iyer",100,"Hypertension"),
      ("AIIA-CTMS-004","AIIA Rheumatoid Arthritis Study","Phase III","Ayurvedic intervention","Dr. Kavya Menon",140,"Rheumatoid Arthritis"),
      ("AIIA-CTMS-005","AIIA Cardiometabolic Prevention Study","Phase III","Integrated Ayurveda protocol","Dr. Rohan Verma",180,"Hyperlipidemia"),
      ("AIIA-CTMS-006","AIIA Healthy Volunteer Safety Study","Phase I","Ayurvedic intervention","Dr. Isha Kapoor",60,"Healthy Volunteer"),
    ]
    studies_by_code = {s.study_code:s for s in db.query(models.Study).all()}
    now = datetime.now(timezone.utc)
    new_studies = []
    for idx,(code,title,phase,intervention,pi,target,condition) in enumerate(study_defs,1):
        if code in studies_by_code:
            continue
        status = "active" if idx < 6 else "planning"
        s=models.Study(study_code=code,title=title,phase=phase,intervention=intervention,principal_investigator=pi,target_enrollment=target,status=status,start_date=now-timedelta(days=120+idx*15),end_date=now+timedelta(days=240),ctri_status="registered" if status=="active" else "pending",ctri_number=f"CTRI/2026/0{idx:02d}/0{12345+idx}" if status=="active" else None,ctri_registration_date=now-timedelta(days=90) if status=="active" else None)
        db.add(s); db.flush(); studies_by_code[code]=s; new_studies.append((s,condition))
        for j,inst in enumerate(["AIIA Main Campus","AIIA South Research Unit","Partner Ayurveda Site"],1):
            site=models.Site(study_id=s.id,site_code=f"{code[-3:]}-S{j:02d}",institution=inst,pi_name=pi,coordinator_name=f"Coordinator {j}",activation_status="activated" if status=="active" else "pending",enrollment_target=max(1,target//3),activated_date=now-timedelta(days=80-j*5) if status=="active" else None)
            db.add(site)
        milestone_defs=[
            ("iec_submission","IEC Submission",-115,"completed"),
            ("iec_approval","IEC Approval",-100,"completed"),
            ("ctri_registration","CTRI Registration",-90,"completed" if status=="active" else "pending"),
            ("site_activation","Site Activation",-80,"completed" if status=="active" else "pending"),
            ("amendment","Protocol Amendment Review",5,"pending"),
            ("monitoring_visit","Next Monitoring Visit",10,"pending"),
            ("close_out","Close-out",240,"pending"),
        ]
        for typ,mname,days,mstatus in milestone_defs:
            planned=now+timedelta(days=days)
            actual=planned if mstatus=="completed" else None
            db.add(models.StudyMilestone(study_id=s.id,milestone_type=typ,name=mname,planned_date=planned,actual_date=actual,status=mstatus))
    db.commit()

    # Only link the trials created by this enrichment, using condition-to-study
    # mapping. Legacy trial/study relationships are left untouched.
    condition_to_study = {}
    for s, condition in new_studies:
        condition_to_study.setdefault(condition, s)
    condition_to_study.setdefault("Healthy Volunteer", studies_by_code.get("AIIA-CTMS-006"))
    for tr in new_trials:
        s = condition_to_study.get(tr.condition)
        if s:
            tr.study_id = s.id
    db.commit()

    # Ten subjects per study gives the CTMS recruitment funnel enough depth to
    # exercise screened -> eligible -> enrolled -> randomized -> completed.
    all_studies = list(db.query(models.Study).order_by(models.Study.id).all())
    statuses=["screened","eligible","enrolled","randomized","completed","enrolled","eligible","enrolled","screened","randomized"]
    for s in all_studies:
        sites=db.query(models.Site).filter(models.Site.study_id==s.id).all()
        if not sites or s.status != "active":
            continue
        current=db.query(models.StudySubject).filter(models.StudySubject.study_id==s.id).count()
        if current >= 10:
            continue
        linked_condition = next((c for st,c in new_studies if st.id==s.id), None)
        candidates=[p for p in all_patients if p.condition == linked_condition] if linked_condition else []
        if not candidates:
            continue
        for k,status in enumerate(statuses):
            p=candidates[(s.id*7+k)%len(candidates)]
            if db.query(models.StudySubject).filter_by(study_id=s.id,patient_id=p.id).first():
                continue
            site=sites[k%len(sites)]
            db.add(models.StudySubject(study_id=s.id,site_id=site.id,patient_id=p.id,subject_code=f"{s.study_code}-SUB-{k+1:03d}",status=status,consent_status="obtained" if status != "screened" else "not_obtained",consent_version="ICF v2.1" if status != "screened" else None,consent_date=now-timedelta(days=30) if status != "screened" else None,enrolled_date=now-timedelta(days=20) if status in ("enrolled","randomized","completed") else None))
        db.flush(); recompute_recruitment(db,s.id)
    db.commit()

    # Coherent synthetic AE/SAE cluster on the first active enriched study.
    active = [s for s in all_studies if s.status == "active"]
    if active:
        s=active[0]
        subjects=db.query(models.StudySubject).filter(models.StudySubject.study_id==s.id).limit(5).all()
        sites=db.query(models.Site).filter(models.Site.study_id==s.id).all()
        if len(subjects)>=3 and db.query(models.SafetyCase).filter(models.SafetyCase.study_id==s.id,models.SafetyCase.batch_number=="AIIA-BATCH-26A").count()==0:
            for k,sub in enumerate(subjects[:3]):
                admin=now-timedelta(days=2,hours=k*4); onset=admin+timedelta(hours=2)
                serious = k == 0
                seriousness = "hospitalization" if serious else "not_serious"
                db.add(models.SafetyCase(study_id=s.id,site_id=sites[0].id if sites else None,patient_id=sub.patient_id,event_term=["Nausea and dizziness","Dizziness and headache","Nausea with fatigue"][k],event_date=onset,is_serious=serious,severity="moderate",seriousness=seriousness,outcome="recovering",causality="possible",status="under_review" if serious else "draft",narrative="Synthetic pharmacovigilance demonstration case; not a clinical finding.",report_due_date=compute_due_date(onset,seriousness),drug="AIIA-Demo-Formulation",batch_number="AIIA-BATCH-26A",dose="500 mg",route="Oral",administration_date=admin,location="Ward B",symptom_onset_date=onset,action_taken="drug_interrupted" if serious else "unknown"))
            db.commit()
            try:
                detect_signals(db,study_id=s.id); db.commit()
            except Exception:
                db.rollback()

    # Operational compliance examples: open deviation + overdue monitoring.
    for s in active[:3]:
        site=db.query(models.Site).filter(models.Site.study_id==s.id).first()
        if not db.query(models.ProtocolDeviation).filter_by(study_id=s.id).first():
            db.add(models.ProtocolDeviation(study_id=s.id,site_id=site.id if site else None,description="Late Week-4 visit window; coordinator review required.",severity="minor",deviation_date=now-timedelta(days=9),resolution_status="open"))
        if not db.query(models.MonitoringVisit).filter_by(study_id=s.id).first():
            db.add(models.MonitoringVisit(study_id=s.id,site_id=site.id if site else None,visit_date=now-timedelta(days=4),findings="Follow-up monitoring visit overdue in synthetic demo.",overdue=True))
    db.commit()
