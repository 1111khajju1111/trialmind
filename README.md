# TrialMind — From Protocol to Patient

## SIH26046 implementation status

| Priority | Scope | Status |
|---|---|---|
| P1 | Core CTMS (studies, sites, milestones, deviations, monitoring) | 🟢 Done |
| P2 | AI Recruitment Module (TrialMind eligibility + matching wired to Study/Subject) | 🟢 Done |
| P3 | Pharmacovigilance MVP (AE/SAE capture, status workflow, deadline engine, safety dashboard) | 🟢 **Done — frozen stable** |
| P4 | Ethics + CTRI + Regulatory Compliance | 🟢 Done |
| P3b | Safety Signal Engine (drug/batch/site/time correlation) | 🟢 Done |
| P5 | Role-Based Access + Audit | 🟢 Done |
| P6 | Consent & Data Protection MVP | 🟢 Done |
| P7 | FHIR + CDISC Demonstrator | 🟢 Done |

Priority 3 hardening pass (frozen): StudySubject-membership validation on
every safety case, strictly sequential Draft → Under Review → Reported →
Closed status transitions, non-overlapping AE/SAE endpoint semantics, and a
configurable-deadline disclaimer surfaced in the API response. Covered by
`backend/tests/test_safety.py`.

Priority 4: `Study.ctri_number/ctri_status/ctri_registration_date`,
`PATCH /studies/{id}/ctri` (auto-syncs a `ctri_registration` milestone),
`GET /studies/{id}/regulatory-timeline` (on_track/due_soon/overdue tri-state
over StudyMilestone), `GET /compliance/alerts` (unified overdue/due-soon
feed across milestones, AE/SAE reports, and monitoring visits), and
`GET /dashboard/regulatory` (portfolio rollup). New milestone types
(`iec_submission`, `ctri_update`, `amendment`) needed no schema change --
`milestone_type` was always free-text. Covered by
`backend/tests/test_compliance.py`. Frontend: the study-level Milestones
tab is now a full regulatory timeline + CTRI editor, and `/compliance` is a
new portfolio-wide dashboard page.


An agentic clinical-trial patient-matching platform: upload a trial protocol,
and an AI agent orchestrates the work of finding candidate patients, running
deterministic eligibility checks, retrieving supporting evidence from the
protocol text, and drafting physician outreach — all under a hard human
approval gate, with every step recorded to an audit trail.

Built for SIH26046 (Smart India Hackathon, Problem Statement 26046 —
Generative AI & Agentic Workflow / Healthcare Innovation tracks). Patient
matching (**TrialMind**) is the deeply-built, demo-ready module; regulatory
drafting and lab scheduling remain in the codebase as secondary/roadmap
features rather than three shallow builds.

## The problem

Matching patients to clinical trials is slow and manual: a coordinator reads
a dense eligibility section, then checks it by hand against each patient's
chart. It doesn't scale, it's inconsistent between reviewers, and there's
usually no clear record of *why* a given patient was judged eligible or not.

## The solution

TrialMind turns the protocol's eligibility criteria into a structured,
machine-checkable rule set, uses that to screen patients deterministically
(never by asking an LLM to "judge" eligibility), retrieves the exact protocol
text that supports each decision, and puts a human coordinator in the loop
before anything reaches a physician. The core claim isn't "we use AI" — it's
that **AI orchestrates the workflow while deterministic rules decide
eligibility, evidence supports every decision, uncertainty is surfaced
rather than hidden, humans retain control, and every action is auditable.**

## Architecture

```
Trial protocol (pasted text or PDF)
    -> LLM extracts structured, checkable criteria (age, HbA1c, LDL, etc.)
    -> Protocol chunked for retrieval (RAG)

Agent run (Groq/Llama, tool-calling):
    search_patients
    -> evaluate_eligibility   (deterministic rules engine, NOT the LLM)
    -> retrieve_evidence      (TF-IDF retrieval over protocol chunks)
    -> LLM writes a rationale grounded in the tool results

Every step logged to a run-scoped audit timeline
    -> Human coordinator reviews the criterion checklist + evidence
    -> Approve / Reject  (NOT_ELIGIBLE candidates cannot be approved, ever)
    -> Outreach draft generated only after approval — never sent automatically
```

**Key principle:** the LLM never decides pass/fail on an objective criterion.
`app/services/eligibility_engine.py` does that in plain Python. The LLM's job
is retrieval-grounded explanation and workflow orchestration via tool
calls — which tools to call, and in what order, is the LLM's own decision,
visible turn-by-turn in the agent timeline.

```
backend/    FastAPI service
  app/services/eligibility_engine.py   deterministic rule checking
  app/services/rag_service.py          chunking + TF-IDF evidence retrieval
  app/services/agent_orchestrator.py   Groq (Llama) tool-use loop, logs every step
  app/routers/trials.py                protocol upload (text or PDF) + criteria extraction
  app/routers/patients.py              agent-driven matching + approval-gated outreach
  app/routers/approvals.py             approve/reject + the NOT_ELIGIBLE safety boundary
  app/routers/audit.py                 run-scoped action timeline
  app/routers/admin.py                 demo-mode-gated reset to known-good seeded state
  app/mock_data.py                     seeded trials (incl. real uploaded protocols) + patients
frontend/   React app (Vite)
  src/pages/TrialMind.jsx              main agent workflow page (run ID + live timeline)
  src/components/ActionTimeline.jsx    step-by-step agent trace
  src/components/CandidateCard.jsx     criterion checklist + evidence + approval + outreach draft
  src/pages/AuditTrail.jsx             full run history + approval log
  src/pages/PatientDirectory.jsx       patient roster with match history
```

## AI workflow: the agent's tools

The orchestrator gives the model three tools and lets it decide the order:

- **`search_patients(condition)`** — pulls candidate patients matching the
  trial's condition.
- **`evaluate_eligibility(patient_id)`** — runs the deterministic engine and
  returns one of four verdicts (below). This result is authoritative; the
  LLM cannot override it.
- **`retrieve_evidence(patient_id, query)`** — TF-IDF retrieval over the
  chunked protocol text, requiring `patient_id` explicitly so evidence is
  never misattributed to the wrong candidate even when several patients are
  evaluated out of order in the same run.

After the tool-calling phase ends, a separate text-only completion produces
the final per-patient rationale — kept as its own call (rather than asking
the same turn to both stop calling tools *and* emit clean JSON) because
that combination is where smaller/faster models are least reliable.

## Deterministic eligibility, not LLM judgment

Every criterion extracted from a protocol carries a `type`
(inclusion/exclusion), a `field`, an `operator`, and — critically — a
`verification_required` flag. If the extractor isn't confident a criterion
is machine-checkable (informed consent, "investigator judgment", symptom
history), it's marked for human review instead of guessing at a rule that
doesn't really fit. Four verdicts come out of this:

| Verdict | Meaning |
|---|---|
| `ELIGIBLE` | All checkable criteria pass, nothing missing |
| `NOT_ELIGIBLE` | A checkable criterion definitively fails |
| `POTENTIAL_MATCH` | Checkable criteria pass, but data is missing for some |
| `VERIFICATION_REQUIRED` | One or more criteria need human judgment |

A 94% "score" with one missing required field is `POTENTIAL_MATCH`, not a
silent pass — the UI never forces a binary result when required data isn't
available, and explicitly lists what's missing.

## Priority 3(b): Safety Signal Engine

`app/services/safety_signals.py` correlates AE/SAE cases (`SafetyCase` rows)
that share a drug + batch number and cluster in time — optionally
concentrated at one site, and within that, at one free-text ward/clinic
`location` (`location_concentration`/`dominant_location`, finer-grained
than site alone) — and raises a `SafetySignal` for human
pharmacovigilance review. It groups cases by (study, drug, batch), chains
them into rolling time-window clusters, scores symptom similarity with
TF-IDF cosine similarity over the reported terms, and blends cluster size,
symptom similarity, and site concentration into a `confidence_score`.
Each case also optionally records `symptom_onset_date` (from which
`onset_latency_hours` is derived relative to `administration_date`) and
`action_taken` (dose unchanged/reduced/drug withdrawn/interrupted) —
standard pharmacovigilance fields shown alongside the cluster-level signal,
not inputs to the correlation itself. **Scope note:** this detects a
statistical correlation worth investigating — it never claims or confirms
"contamination," never auto-escalates, and never auto-dismisses. Every
signal starts `open` and requires a human (`Pharmacovigilance` role) to
move it to `under_review` and then to a terminal `escalated` or
`dismissed` state. Covered by `backend/tests/test_safety_signals.py` and
`backend/tests/test_safety.py`.

## Priority 5: Role-Based Access + Audit

`app/rbac.py` defines the seven SIH26046 roles (Principal Investigator,
Study Coordinator, Monitor, Ethics Committee, Pharmacovigilance,
Administrator, Regulator) and resolves the acting role from the
`X-User-Role` header sent by the frontend's role switcher. A single
`main.py` middleware enforces the `Regulator` role's read-only restriction
globally, so no future write endpoint can forget to exclude it. This is
deliberately a thin, demo-appropriate RBAC layer — no login/session/password
— not a production identity provider; see `app/rbac.py`'s docstring for the
full rationale.

## Priority 6: Consent & Data Protection MVP

`StudySubject.consent_status/consent_version/consent_date` track informed
consent per subject (`app/routers/studies.py`). Consent must be recorded as
`obtained` before a subject can be enrolled — enforced server-side, not just
hidden in the UI — matching standard GCP/DPDP practice that consent
precedes any study procedure. Every consent status change is written to the
study's audit log.

## Priority 7: FHIR + CDISC Demonstrator

`app/services/interop.py` and `app/routers/interop.py` expose
`GET /interop/fhir/{resource}` (FHIR R4 Bundles built live from the seeded
data), `GET /interop/mapping` (a human-readable internal-field → FHIR/SDTM
mapping doc), and `GET /export/sdtm/{domain}` (SDTM-style CSV export for
DM and AE domains). The frontend's Interoperability page renders these.

## Control Tower & Human-in-the-Loop

`GET /dashboard/portfolio` reports six portfolio-wide numbers in one
place — active trials, enrollment, AE/SAE, open Safety Signals (distinct
from open safety *cases*), and regulatory/monitoring alert counts split
out of the same `compliance.build_alerts()` feed the Regulatory page
uses — rendered as an always-visible "Control Tower" panel at the top of
the Dashboard (not tucked inside the collapsible Operational Modules
section below it). Covered by `backend/tests/test_dashboard.py`.

Every AI-assisted output in the app — the eligibility verdict, the
AI-drafted outreach email, the AI-drafted regulatory section, and the
algorithmically-detected Safety Signal — carries a consistent
`HumanInLoopBadge` (`frontend/src/components/ui/HumanInLoopBadge.jsx`)
in addition to whatever review/approval gate already exists for that
flow, so no AI-assisted content in the app is unlabeled.

A permanent, always-rendered banner (`DemoBanner.jsx`, not conditional on
a backend health check) reads "DEMO ENVIRONMENT · SYNTHETIC DATA · NOT
FOR CLINICAL DECISION-MAKING" on every page.

## RAG: evidence, not vibes

Protocol text is chunked and retrieved with TF-IDF + cosine similarity
(`app/services/rag_service.py`) — no external embeddings API, so retrieval
works with no network dependency beyond the LLM call itself. Results below a
minimum relevance threshold are filtered out rather than shown as if they
were supporting evidence. Every returned chunk carries a `chunk_id` and
relevance score, so a coordinator (or a judge) can trace any rationale back
to the exact protocol text that grounds it.

## Human approval, always

`POST /approvals/` is the only way a match's status changes. Approving or
rejecting an already-decided record is rejected outright (or returns a
no-op if it's the same decision again) so the audit trail can never end up
with contradictory entries. **A deterministically `NOT_ELIGIBLE` candidate
can never be approved** — this is enforced server-side, not just hidden in
the UI, so no client can bypass it.

Outreach is generated only after approval, and is always presented as
**DRAFT — NOT SENT**: it's recorded for coordinator review, never
transmitted automatically. In demo mode (the default), real email sending
is force-disabled even if a Resend API key happens to be configured — the
demo should never be one misconfigured environment variable away from
actually emailing a synthetic patient record.

## Auditability

`POST /patients/match/start` returns a `run_id` immediately (the agent runs
as a background task), and the frontend polls `GET /audit/timeline/{run_id}`
so the full sequence — protocol loaded, patients discovered, each
eligibility check, each evidence retrieval, ranking, completion — is visible
live instead of behind a spinner. Every timeline event and every approval
log entry carries the run ID, a timestamp, and (for approvals) the acting
coordinator, so any decision can be traced end-to-end: which run produced
it, what evidence supported it, and who approved it.

## Demo mode & reset

`DEMO_MODE=true` (the default) labels the environment as synthetic data,
force-disables real outreach sending regardless of other configuration, and
is required for `POST /admin/reset` to be reachable at all — a destructive
"wipe everything and reseed" endpoint has no business being callable outside
a demo build. Reset restores the full seeded dataset (six trials, patients,
and their protocol chunks) to a known-good state in one call, so the same
presentation can be repeated exactly without redeploying.

## The hero demo path — LIPID-2

The guaranteed, rehearsed path for a live demo:

```
Reset Demo → select LIPID-2 → Run Matching Agent
  ✓ Protocol loaded → ✓ Patients discovered → ✓ Eligibility → ✓ Evidence → ✓ Human review
A. Torres — ELIGIBLE — all criteria pass
  → View evidence trace (protocol chunk, relevance, source text)
  → Approve
  → Generate Outreach Draft → DRAFT — NOT SENT
  → Audit timeline shows the complete run
```

LIPID-2 was specifically seeded with only machine-checkable criteria (no
`verification_required` items), and patient **A. Torres** has data for every
one of them — so this path reaches a clean `ELIGIBLE` deterministically,
every time, from a fresh reset. Five other trials (GLYCO-3, ARTHRIX-1, and
three seeded from real uploaded protocol PDFs — ARTHRIX-2, GLYCO-4, LIPID-3)
are also available to show the messier, more realistic case where several
criteria genuinely need a human.

## Testing

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

- **`test_eligibility.py`** — unit tests of the deterministic rules engine:
  pass/fail on age, HbA1c, BMI, etc.; missing data never silently becomes a
  pass; inclusion vs. exclusion semantics; verification-required criteria
  are never turned into an invented rule; all four verdicts are reachable.
- **`test_rag.py`** — chunking and TF-IDF retrieval: relevance ranking, the
  minimum-relevance filter, chunk IDs returned for traceability.
- **`test_matching.py`** — the core evidence-isolation regression test:
  evaluates several patients, then requests evidence for them in a
  *scrambled* order via a mocked Groq tool-calling loop, and asserts each
  patient's evidence never leaks onto another patient's record.
- **`test_approvals.py`** — approve-once succeeds; approving twice is a
  no-op; rejecting an already-decided record is blocked.
- **`test_outreach.py`** — outreach is blocked before approval, allowed
  after, idempotent (doesn't re-call the LLM on a second request), and an
  LLM failure during generation doesn't leave a corrupted draft.
- **`test_golden_path.py`** — the automated version of the hero demo above:
  reset-equivalent seed → run the agent on the real seeded LIPID-2 trial →
  assert A. Torres reaches `ELIGIBLE` with patient-scoped evidence → approve
  → generate a draft → confirm it's never marked sent → confirm the audit
  timeline records the full run. Also covers the `NOT_ELIGIBLE`-can't-be-
  approved safety boundary directly at the API level.

All of these mock the Groq client, so the full suite runs with no network
access and no API key — safe for CI and for a final check before walking
into a demo.

```bash
cd frontend
npm ci
npm run build
```

## Setup

### 1. Database — Aiven PostgreSQL

1. In the Aiven console, create a PostgreSQL service.
2. Copy the **Service URI** from Overview (looks like
   `postgresql://avnadmin:xxxx@host:port/defaultdb?sslmode=require`).
3. pgvector is not required — retrieval uses in-memory TF-IDF over protocol
   chunks stored as plain rows.

### 2. Backend — Render

1. Push this repo to GitHub.
2. In Render, create a **New Web Service**, connect the repo, root
   directory `backend`.
3. Build command `pip install -r requirements.txt`, start command
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Environment variables (copy `backend/.env.example`, then fill in real
   values — **never commit the filled-in file**):
   - `DATABASE_URL` — Aiven service URI
   - `GROQ_API_KEY` — your Groq API key
   - `GROQ_MODEL` — `llama-3.3-70b-versatile` (single source of truth; the
     app never hard-codes a model name outside this setting)
   - `CORS_ORIGINS` — your deployed frontend URL(s), comma-separated —
     restrict this to the actual origins you use, never `*`
   - `RESEND_API_KEY` / `RESEND_FROM` — optional; outreach still never
     auto-sends while `DEMO_MODE=true`
   - `DEMO_MODE` — `true` for a hackathon/demo deployment. Set to `false`
     only for a build that also has real authentication in front of
     `/admin/reset` and real patient data governance in place.
5. Deploy. On first startup, tables are created and the demo dataset is
   seeded automatically.
6. Confirm it's live: `https://your-backend.onrender.com/health`.

### 3. Frontend — Vercel

1. Import the repo, root directory `frontend`, framework preset Vite.
2. Environment variable: `VITE_API_URL` — your Render backend URL.
3. Deploy, then set the backend's `CORS_ORIGINS` to the exact Vercel URL
   and redeploy the backend.

### 4. Local development

Backend:
```bash
cd backend
cp .env.example .env   # fill in your own values -- never commit .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
cp .env.example .env   # set VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

## Limitations

This is a hackathon prototype, not a clinical system, and should be
described accordingly:

- **Synthetic data only.** All trials and patients are demo/synthetic data
  (including the three seeded from real protocol PDFs — the protocol text
  is real, the patient records are not). No real EHR/LIMS integration.
- **Not a clinical decision-making system.** Deterministic checks and AI
  rationale support a human coordinator's review; they do not make or
  substitute for a clinical or regulatory eligibility determination.
- **Simplified demo authentication.** Approvals are attributed to a single
  hard-coded demo actor, not a real authenticated user/role system.
- **No formal compliance validation.** The architecture includes
  compliance-oriented controls (audit logging, hard approval gates, a
  NOT_ELIGIBLE safety boundary) but has not undergone HIPAA / GxP / 21 CFR
  Part 11 validation and should not be described as compliant.
- **Lab scheduling and regulatory drafting** remain at MVP-scaffold depth —
  patient matching is the deeply-built module.

## Roadmap

- Real EHR/LIMS integration behind a proper data-access layer
- Production authentication and role-based access control
- Formal compliance validation for the audit/approval architecture
- Deepen regulatory drafting and lab scheduling to match TrialMind's depth
