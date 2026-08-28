import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";

const TABS = ["Overview", "Sites", "Subjects", "Milestones", "Deviations", "Monitoring", "Safety"];

const MILESTONE_TYPES = [
  "iec_submission", "iec_approval", "ctri_registration", "ctri_update", "amendment",
  "site_activation", "first_patient_in", "last_patient_in", "close_out", "other",
];

const SUBJECT_STATUSES = ["screened", "eligible", "enrolled", "randomized", "completed", "withdrawn"];

const STATUS_BADGE = {
  planning: "normal", active: "approved", paused: "high",
  completed: "approved", terminated: "rejected",
  pending: "normal", activated: "approved", closed: "rejected",
  overdue: "rejected", open: "high", under_review: "high", resolved: "approved",
  screened: "normal", eligible: "high", enrolled: "approved",
  randomized: "approved", withdrawn: "rejected",
  minor: "normal", major: "high", critical: "rejected",
  // Priority 4: CTRI status + regulatory due_status badges
  registered: "approved", not_registered: "normal",
  due_soon: "high", on_track: "approved",
  // Priority 6: consent status badges
  not_obtained: "normal", obtained: "approved",
};

function badge(status) {
  return <span className={`badge ${STATUS_BADGE[status] || "normal"}`}>{(status || "").replace("_", " ")}</span>;
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString() : "—";
}

export default function StudyDetail() {
  const { id } = useParams();
  const studyId = Number(id);
  const [tab, setTab] = useState("Overview");
  const [detail, setDetail] = useState(null);
  const [sites, setSites] = useState([]);
  const [milestones, setMilestones] = useState([]);
  const [deviations, setDeviations] = useState([]);
  const [visits, setVisits] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAll = () => {
    setLoading(true);
    Promise.all([
      api.getStudy(studyId),
      api.getSites(studyId),
      api.getMilestones(studyId),
      api.getDeviations(studyId),
      api.getMonitoringVisits(studyId),
      api.getStudySubjects(studyId),
      api.getPatients(),
    ])
      .then(([d, s, m, dev, v, subj, p]) => {
        setDetail(d.data);
        setSites(s.data);
        setMilestones(m.data);
        setDeviations(dev.data);
        setVisits(v.data);
        setSubjects(subj.data);
        setPatients(p.data);
      })
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadAll(); }, [studyId]);

  // Reload just the study summary (recruitment counters, rollups) without a
  // full page reload -- used after subject / deviation / milestone changes.
  const refreshSummary = () => {
    api.getStudy(studyId).then((res) => setDetail(res.data)).catch(() => {});
  };

  if (loading) return <p className="loading">Loading...</p>;
  if (error) return <div className="alert-box">{error}</div>;
  if (!detail) return null;

  const study = detail.study;
  const funnel = [
    { label: "Screened", value: study.screened_count },
    { label: "Eligible", value: study.eligible_count },
    { label: "Enrolled", value: study.enrolled_count },
    { label: "Randomized", value: study.randomized_count },
    { label: "Completed", value: study.completed_count },
  ];
  const maxFunnel = Math.max(1, ...funnel.map((f) => f.value));

  return (
    <div>
      <Link to="/studies" style={{ fontSize: 12.5, color: "var(--accent-cyan)", fontWeight: 600 }}>
        ← All studies
      </Link>
      <h1 style={{ marginTop: 8 }}>{study.study_code} — {study.title}</h1>
      <p className="subtitle">
        {study.phase || "Phase n/a"} · PI: {study.principal_investigator || "unassigned"} ·{" "}
        {badge(study.status)}
        {detail.linked_trial && (
          <> · Linked protocol: <Link to="/trialmind" style={{ color: "var(--accent-cyan)" }}>{detail.linked_trial.name}</Link></>
        )}
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`gbtn ${tab === t ? "gbtn-primary" : "gbtn-secondary"}`}
            style={{ padding: "8px 16px", fontSize: 13 }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && (
        <OverviewTab detail={detail} funnel={funnel} maxFunnel={maxFunnel} />
      )}
      {tab === "Sites" && (
        <SitesTab studyId={studyId} sites={sites} onChange={() => { loadAll(); }} />
      )}
      {tab === "Subjects" && (
        <SubjectsTab
          studyId={studyId} subjects={subjects} sites={sites} patients={patients}
          onChange={() => { api.getStudySubjects(studyId).then((r) => setSubjects(r.data)); refreshSummary(); }}
        />
      )}
      {tab === "Milestones" && (
        <MilestonesTab
          studyId={studyId}
          onChange={() => { api.getMilestones(studyId).then((r) => setMilestones(r.data)); refreshSummary(); }}
        />
      )}
      {tab === "Deviations" && (
        <DeviationsTab
          studyId={studyId} deviations={deviations} sites={sites}
          onChange={() => { api.getDeviations(studyId).then((r) => setDeviations(r.data)); refreshSummary(); }}
        />
      )}
      {tab === "Monitoring" && (
        <MonitoringTab
          studyId={studyId} visits={visits} sites={sites}
          onChange={() => { api.getMonitoringVisits(studyId).then((r) => setVisits(r.data)); refreshSummary(); }}
        />
      )}
      {tab === "Safety" && (
        <SafetyTab studyId={studyId} sites={sites} subjects={subjects} />
      )}
    </div>
  );
}

function OverviewTab({ detail, funnel, maxFunnel }) {
  const study = detail.study;
  return (
    <div>
      <div className="kpi-grid">
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon">🏢</div>
          <div className="kpi-card-value">{detail.site_count}</div>
          <div className="kpi-card-label">Sites ({detail.activated_site_count} activated)</div>
        </GlassCard>
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon">🧑‍🤝‍🧑</div>
          <div className="kpi-card-value">{detail.subject_count}</div>
          <div className="kpi-card-label">Subjects on record</div>
        </GlassCard>
        <GlassCard className="kpi-card" glow={detail.open_deviation_count > 0 ? "warning" : undefined}>
          <div className="kpi-card-icon">⚠️</div>
          <div className="kpi-card-value">{detail.open_deviation_count}</div>
          <div className="kpi-card-label">Open protocol deviations</div>
        </GlassCard>
        <GlassCard className="kpi-card" glow={detail.overdue_milestone_count > 0 ? "warning" : undefined}>
          <div className="kpi-card-icon">📅</div>
          <div className="kpi-card-value">{detail.overdue_milestone_count}</div>
          <div className="kpi-card-label">Overdue milestones</div>
        </GlassCard>
      </div>

      <div className="section-heading">
        <span className="section-heading-icon">📈</span> Recruitment Funnel
      </div>
      <GlassCard>
        {funnel.map((f) => (
          <div key={f.label} style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 3 }}>
              <span style={{ color: "var(--text-secondary)" }}>{f.label}</span>
              <strong>{f.value}</strong>
            </div>
            <div style={{ height: 8, borderRadius: 4, background: "var(--bg-secondary)", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${(f.value / maxFunnel) * 100}%`,
                  background: "var(--gradient-success, var(--accent-emerald))",
                  transition: "width 0.4s ease",
                }}
              />
            </div>
          </div>
        ))}
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "10px 0 0" }}>
          Withdrawn: {study.withdrawn_count} · Target enrollment: {study.target_enrollment}
        </p>
      </GlassCard>

      <div className="section-heading">
        <span className="section-heading-icon">ℹ️</span> Study Details
      </div>
      <GlassCard>
        <p style={{ fontSize: 13, margin: "4px 0" }}><strong>Intervention:</strong> {study.intervention || "—"}</p>
        <p style={{ fontSize: 13, margin: "4px 0" }}><strong>Start date:</strong> {fmtDate(study.start_date)}</p>
        <p style={{ fontSize: 13, margin: "4px 0" }}><strong>End date:</strong> {fmtDate(study.end_date)}</p>
      </GlassCard>
    </div>
  );
}

function SitesTab({ studyId, sites, onChange }) {
  const [form, setForm] = useState({ institution: "", site_code: "", pi_name: "", coordinator_name: "", enrollment_target: 50, activation_status: "pending" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api.createSite(studyId, { ...form, enrollment_target: Number(form.enrollment_target) || 0 });
      setForm({ institution: "", site_code: "", pi_name: "", coordinator_name: "", enrollment_target: 50, activation_status: "pending" });
      onChange();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not create site.");
    } finally { setBusy(false); }
  };

  return (
    <div>
      <GlassCard glow="ai">
        <div className="card-header"><strong>Add Site</strong></div>
        <form onSubmit={submit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Institution</label>
              <input required value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} />
            </div>
            <div>
              <label>Site code</label>
              <input value={form.site_code} onChange={(e) => setForm({ ...form, site_code: e.target.value })} placeholder="SITE-03" />
            </div>
            <div>
              <label>Site PI</label>
              <input value={form.pi_name} onChange={(e) => setForm({ ...form, pi_name: e.target.value })} />
            </div>
            <div>
              <label>Coordinator</label>
              <input value={form.coordinator_name} onChange={(e) => setForm({ ...form, coordinator_name: e.target.value })} />
            </div>
            <div>
              <label>Enrollment target</label>
              <input type="number" min="0" value={form.enrollment_target} onChange={(e) => setForm({ ...form, enrollment_target: e.target.value })} />
            </div>
            <div>
              <label>Activation status</label>
              <select value={form.activation_status} onChange={(e) => setForm({ ...form, activation_status: e.target.value })}>
                <option value="pending">pending</option>
                <option value="activated">activated</option>
                <option value="closed">closed</option>
              </select>
            </div>
          </div>
          {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
          <GradientButton variant="primary" type="submit" disabled={busy}>{busy ? "Adding..." : "Add Site"}</GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading"><span className="section-heading-icon">🏢</span> Sites ({sites.length})</div>
      {sites.length === 0 && <GlassCard>No sites yet.</GlassCard>}
      <div className="agent-grid" style={{ marginTop: 12 }}>
        {sites.map((s) => (
          <GlassCard key={s.id}>
            <div className="card-header">
              <strong>{s.institution}</strong>
              {badge(s.activation_status)}
            </div>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "2px 0" }}>
              {s.site_code || "no code"} · PI: {s.pi_name || "—"} · Coordinator: {s.coordinator_name || "—"}
            </p>
            <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
              Enrollment target: {s.enrollment_target} · Activated: {fmtDate(s.activated_date)}
            </p>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}

function SubjectsTab({ studyId, subjects, sites, patients, onChange }) {
  const [form, setForm] = useState({ patient_id: "", site_id: "", status: "screened", notes: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const alreadyAdded = useMemo(() => new Set(subjects.map((s) => s.patient_id)), [subjects]);
  const availablePatients = patients.filter((p) => !alreadyAdded.has(p.id));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.patient_id) { setErr("Choose a patient."); return; }
    setBusy(true); setErr(null);
    try {
      await api.createStudySubject(studyId, {
        patient_id: Number(form.patient_id),
        site_id: form.site_id ? Number(form.site_id) : null,
        status: form.status,
        notes: form.notes || null,
      });
      setForm({ patient_id: "", site_id: "", status: "screened", notes: "" });
      onChange();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not add subject.");
    } finally { setBusy(false); }
  };

  const advance = async (subject, status) => {
    await api.updateStudySubject(studyId, subject.id, { status });
    onChange();
  };

  // Priority 2: eligible -> enrolled is a dedicated, explicit action (not
  // just another generic status hop) so "enrolling a patient" reads as the
  // distinct clinical decision it is: AI Approved -> Eligible -> [Enroll
  // Patient] -> Enrolled.
  const enroll = async (subject) => {
    setErr(null);
    try {
      await api.enrollStudySubject(studyId, subject.id);
      onChange();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not enroll this patient.");
    }
  };

  const recordConsent = async (subject, consent_status) => {
    setErr(null);
    try {
      await api.updateStudySubject(studyId, subject.id, {
        consent_status,
        consent_version: consent_status === "obtained" ? "AIIA-ICF-v1.2" : subject.consent_version,
        consent_date: consent_status === "obtained" ? new Date().toISOString() : subject.consent_date,
      });
      onChange();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not update consent.");
    }
  };

  return (
    <div>
      <GlassCard glow="ai">
        <div className="card-header"><strong>Add Subject (Patient → Study → Site)</strong></div>
        <form onSubmit={submit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Patient</label>
              <select value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })}>
                <option value="">Select a patient...</option>
                {availablePatients.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.condition || "no condition on file"})</option>
                ))}
              </select>
            </div>
            <div>
              <label>Site</label>
              <select value={form.site_id} onChange={(e) => setForm({ ...form, site_id: e.target.value })}>
                <option value="">Unassigned</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.institution}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Initial status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                {SUBJECT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label>Notes</label>
              <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
          </div>
          {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
          <GradientButton variant="primary" type="submit" disabled={busy}>{busy ? "Adding..." : "Add Subject"}</GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading"><span className="section-heading-icon">🧑‍🤝‍🧑</span> Subjects ({subjects.length})</div>
      {subjects.length === 0 && <GlassCard>No subjects yet.</GlassCard>}
      {subjects.map((s) => {
        const idx = SUBJECT_STATUSES.indexOf(s.status);
        const next = s.status !== "withdrawn" && s.status !== "completed" ? SUBJECT_STATUSES[idx + 1] : null;
        // The eligible -> enrolled hop gets its own explicit button/endpoint
        // instead of the generic "Advance to" one -- see enroll() above.
        const isEnrollStep = s.status === "eligible" && next === "enrolled";
        return (
          <GlassCard key={s.id}>
            <div className="card-header">
              <strong>{s.patient_name}</strong>
              <span style={{ display: "flex", gap: 6 }}>
                {badge(s.status)}
                <span
                  className={`badge ${STATUS_BADGE[s.consent_status] || "normal"}`}
                  title="Consent status (Priority 6 — Consent & Data Protection)"
                >
                  consent: {(s.consent_status || "not_obtained").replace("_", " ")}
                </span>
              </span>
            </div>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "2px 0" }}>
              {s.subject_code ? `${s.subject_code} · ` : ""}Site: {s.site_name || "unassigned"}
              {s.enrolled_date ? ` · Enrolled ${fmtDate(s.enrolled_date)}` : ""}
              {s.consent_date ? ` · Consent recorded ${fmtDate(s.consent_date)}` : ""}
            </p>
            {s.notes && <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0" }}>{s.notes}</p>}
            {isEnrollStep && s.consent_status !== "obtained" && (
              <p style={{ fontSize: 12, color: "var(--accent-amber)", margin: "4px 0" }}>
                Informed consent must be recorded before this subject can be enrolled.
              </p>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              {isEnrollStep ? (
                s.consent_status === "obtained" ? (
                  <GradientButton variant="ai" onClick={() => enroll(s)}>
                    Enroll Patient
                  </GradientButton>
                ) : (
                  <GradientButton variant="secondary" onClick={() => recordConsent(s, "obtained")}>
                    Record Informed Consent
                  </GradientButton>
                )
              ) : (
                next && (
                  <GradientButton variant="primary" onClick={() => advance(s, next)}>
                    Advance to {next}
                  </GradientButton>
                )
              )}
              {s.consent_status === "not_obtained" && !isEnrollStep && (
                <GradientButton variant="secondary" onClick={() => recordConsent(s, "obtained")}>
                  Record Consent
                </GradientButton>
              )}
              {s.consent_status === "obtained" && (
                <GradientButton variant="danger" onClick={() => recordConsent(s, "withdrawn")}>
                  Withdraw Consent
                </GradientButton>
              )}
              {s.status !== "withdrawn" && s.status !== "completed" && (
                <GradientButton variant="danger" onClick={() => advance(s, "withdrawn")}>
                  Withdraw
                </GradientButton>
              )}
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
}

function MilestonesTab({ studyId, onChange: parentOnChange }) {
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ milestone_type: "iec_approval", name: "", planned_date: "", actual_date: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const [ctriForm, setCtriForm] = useState({ ctri_number: "", ctri_status: "not_registered", ctri_registration_date: "" });
  const [ctriBusy, setCtriBusy] = useState(false);
  const [ctriErr, setCtriErr] = useState(null);

  const load = () => {
    setLoading(true);
    api.getRegulatoryTimeline(studyId).then((r) => {
      setTimeline(r.data);
      setCtriForm({
        ctri_number: r.data.ctri_number || "",
        ctri_status: r.data.ctri_status || "not_registered",
        ctri_registration_date: r.data.ctri_registration_date ? r.data.ctri_registration_date.slice(0, 10) : "",
      });
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [studyId]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setErr("Name is required."); return; }
    setBusy(true); setErr(null);
    try {
      await api.createMilestone(studyId, {
        milestone_type: form.milestone_type,
        name: form.name,
        planned_date: form.planned_date || null,
        actual_date: form.actual_date || null,
      });
      setForm({ milestone_type: "iec_approval", name: "", planned_date: "", actual_date: "" });
      load();
      parentOnChange?.();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not create milestone.");
    } finally { setBusy(false); }
  };

  const submitCtri = async (e) => {
    e.preventDefault();
    setCtriBusy(true); setCtriErr(null);
    try {
      await api.updateCTRI(studyId, {
        ctri_number: ctriForm.ctri_number || null,
        ctri_status: ctriForm.ctri_status,
        ctri_registration_date: ctriForm.ctri_registration_date || null,
      });
      load();
      parentOnChange?.();
    } catch (e2) {
      setCtriErr(e2?.response?.data?.detail || "Could not update CTRI details.");
    } finally { setCtriBusy(false); }
  };

  if (loading || !timeline) return <p className="loading">Loading...</p>;

  return (
    <div>
      <GlassCard glow={timeline.ctri_status === "registered" ? "success" : "ai"}>
        <div className="card-header">
          <strong>CTRI Registration</strong>
          {badge(timeline.ctri_status)}
        </div>
        <form onSubmit={submitCtri}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div>
              <label>CTRI number</label>
              <input
                value={ctriForm.ctri_number}
                onChange={(e) => setCtriForm({ ...ctriForm, ctri_number: e.target.value })}
                placeholder="CTRI/2026/01/000123"
              />
            </div>
            <div>
              <label>Status</label>
              <select value={ctriForm.ctri_status} onChange={(e) => setCtriForm({ ...ctriForm, ctri_status: e.target.value })}>
                <option value="not_registered">not registered</option>
                <option value="pending">pending</option>
                <option value="registered">registered</option>
              </select>
            </div>
            <div>
              <label>Registration date</label>
              <input
                type="date"
                value={ctriForm.ctri_registration_date}
                onChange={(e) => setCtriForm({ ...ctriForm, ctri_registration_date: e.target.value })}
              />
            </div>
          </div>
          {ctriErr && <div className="alert-box" style={{ marginTop: 8 }}>{ctriErr}</div>}
          <GradientButton variant="secondary" type="submit" disabled={ctriBusy}>
            {ctriBusy ? "Saving..." : "Save CTRI Details"}
          </GradientButton>
        </form>
      </GlassCard>

      <div className="kpi-grid">
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon">🟢</div>
          <div className="kpi-card-value">{timeline.summary.on_track}</div>
          <div className="kpi-card-label">On Track</div>
        </GlassCard>
        <GlassCard className="kpi-card" glow={timeline.summary.due_soon > 0 ? "warning" : undefined}>
          <div className="kpi-card-icon">🟡</div>
          <div className="kpi-card-value">{timeline.summary.due_soon}</div>
          <div className="kpi-card-label">Due Soon</div>
        </GlassCard>
        <GlassCard className="kpi-card" glow={timeline.summary.overdue > 0 ? "warning" : undefined}>
          <div className="kpi-card-icon">🔴</div>
          <div className="kpi-card-value">{timeline.summary.overdue}</div>
          <div className="kpi-card-label">Overdue</div>
        </GlassCard>
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon">✅</div>
          <div className="kpi-card-value">{timeline.summary.completed}</div>
          <div className="kpi-card-label">Completed</div>
        </GlassCard>
      </div>
      {timeline.deadline_disclaimer && (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "-6px 0 16px" }}>
          {timeline.deadline_disclaimer}
        </p>
      )}

      <GlassCard glow="ai">
        <div className="card-header"><strong>Add Milestone (IEC / CTRI / Amendment / Site / Enrollment)</strong></div>
        <form onSubmit={submit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Type</label>
              <select value={form.milestone_type} onChange={(e) => setForm({ ...form, milestone_type: e.target.value })}>
                {MILESTONE_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label>Name</label>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="IEC Approval" />
            </div>
            <div>
              <label>Planned date</label>
              <input type="date" value={form.planned_date} onChange={(e) => setForm({ ...form, planned_date: e.target.value })} />
            </div>
            <div>
              <label>Actual date (leave blank if not done)</label>
              <input type="date" value={form.actual_date} onChange={(e) => setForm({ ...form, actual_date: e.target.value })} />
            </div>
          </div>
          {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
          <GradientButton variant="primary" type="submit" disabled={busy}>{busy ? "Adding..." : "Add Milestone"}</GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading"><span className="section-heading-icon">📅</span> Regulatory Timeline ({timeline.milestones.length})</div>
      {timeline.milestones.length === 0 && <GlassCard>No milestones yet.</GlassCard>}
      {timeline.milestones.map((m) => (
        <GlassCard key={m.id} glow={m.due_status === "overdue" ? "warning" : undefined}>
          <div className="card-header">
            <strong>{m.is_regulatory ? "⚖️ " : ""}{m.name}</strong>
            <div style={{ display: "flex", gap: 6 }}>
              {badge(m.status)}
              {m.due_status && badge(m.due_status)}
            </div>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>
            {m.milestone_type.replace(/_/g, " ")} · Planned {fmtDate(m.planned_date)}
            {m.actual_date ? ` · Completed ${fmtDate(m.actual_date)}` : ""}
          </p>
        </GlassCard>
      ))}
    </div>
  );
}

function DeviationsTab({ studyId, deviations, sites, onChange }) {
  const [form, setForm] = useState({ description: "", severity: "minor", site_id: "", deviation_date: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.description.trim()) { setErr("Description is required."); return; }
    setBusy(true); setErr(null);
    try {
      await api.createDeviation(studyId, {
        description: form.description,
        severity: form.severity,
        site_id: form.site_id ? Number(form.site_id) : null,
        deviation_date: form.deviation_date || null,
      });
      setForm({ description: "", severity: "minor", site_id: "", deviation_date: "" });
      onChange();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not record deviation.");
    } finally { setBusy(false); }
  };

  return (
    <div>
      <GlassCard glow="ai">
        <div className="card-header"><strong>Record Protocol Deviation</strong></div>
        <form onSubmit={submit}>
          <label>Description</label>
          <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div>
              <label>Severity</label>
              <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                <option value="minor">minor</option>
                <option value="major">major</option>
                <option value="critical">critical</option>
              </select>
            </div>
            <div>
              <label>Site</label>
              <select value={form.site_id} onChange={(e) => setForm({ ...form, site_id: e.target.value })}>
                <option value="">Unspecified</option>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.institution}</option>)}
              </select>
            </div>
            <div>
              <label>Date</label>
              <input type="date" value={form.deviation_date} onChange={(e) => setForm({ ...form, deviation_date: e.target.value })} />
            </div>
          </div>
          {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
          <GradientButton variant="primary" type="submit" disabled={busy}>{busy ? "Recording..." : "Record Deviation"}</GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading"><span className="section-heading-icon">⚠️</span> Protocol Deviations ({deviations.length})</div>
      {deviations.length === 0 && <GlassCard>No deviations recorded.</GlassCard>}
      {deviations.map((d) => (
        <GlassCard key={d.id}>
          <div className="card-header">
            <span>{badge(d.severity)}</span>
            {badge(d.resolution_status)}
          </div>
          <p style={{ fontSize: 13, margin: "4px 0" }}>{d.description}</p>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>{fmtDate(d.deviation_date)}</p>
        </GlassCard>
      ))}
    </div>
  );
}

function MonitoringTab({ studyId, visits, sites, onChange }) {
  const [form, setForm] = useState({ site_id: "", visit_date: "", findings: "", overdue: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api.createMonitoringVisit(studyId, {
        site_id: form.site_id ? Number(form.site_id) : null,
        visit_date: form.visit_date || null,
        findings: form.findings || null,
        overdue: form.overdue,
      });
      setForm({ site_id: "", visit_date: "", findings: "", overdue: false });
      onChange();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Could not record monitoring visit.");
    } finally { setBusy(false); }
  };

  return (
    <div>
      <GlassCard glow="ai">
        <div className="card-header"><strong>Record Monitoring Visit</strong></div>
        <form onSubmit={submit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Site</label>
              <select value={form.site_id} onChange={(e) => setForm({ ...form, site_id: e.target.value })}>
                <option value="">Unspecified</option>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.institution}</option>)}
              </select>
            </div>
            <div>
              <label>Visit date</label>
              <input type="date" value={form.visit_date} onChange={(e) => setForm({ ...form, visit_date: e.target.value })} />
            </div>
          </div>
          <label>Findings</label>
          <textarea rows={3} value={form.findings} onChange={(e) => setForm({ ...form, findings: e.target.value })} />
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={form.overdue}
              onChange={(e) => setForm({ ...form, overdue: e.target.checked })}
            />
            Flag as overdue
          </label>
          {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
          <GradientButton variant="primary" type="submit" disabled={busy}>{busy ? "Recording..." : "Record Visit"}</GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading"><span className="section-heading-icon">🔍</span> Monitoring Visits ({visits.length})</div>
      {visits.length === 0 && <GlassCard>No monitoring visits recorded.</GlassCard>}
      {visits.map((v) => (
        <GlassCard key={v.id}>
          <div className="card-header">
            <strong>{fmtDate(v.visit_date)}</strong>
            {v.overdue && badge("overdue")}
          </div>
          <p style={{ fontSize: 13, margin: 0 }}>{v.findings || "No findings recorded."}</p>
        </GlassCard>
      ))}
    </div>
  );
}

// Priority 3 -- study-scoped pharmacovigilance view. Deliberately uses its
// own badge maps rather than the page-wide badge()/STATUS_BADGE above:
// "closed" already means something different (and red) for a Site's
// activation_status, so a safety case being "closed" (resolved, good news)
// must not borrow that color.
const SAFETY_STATUS_FLOW = ["draft", "under_review", "reported", "closed"];
const SAFETY_STATUS_BADGE = { draft: "normal", under_review: "high", reported: "approved", closed: "normal" };
const SAFETY_SEVERITY_BADGE = { mild: "normal", moderate: "high", severe: "rejected" };
const SAFETY_DUE_BADGE = { overdue: "rejected", approaching: "high", on_track: "approved" };

function safetyBadge(map, value) {
  return <span className={`badge ${map[value] || "normal"}`}>{(value || "").replace(/_/g, " ")}</span>;
}

function fmtDateTime(d) {
  return d ? new Date(d).toLocaleString() : "—";
}

function SafetyTab({ studyId, sites, subjects }) {
  const [dash, setDash] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    site_id: "", patient_id: "", event_term: "", event_date: "",
    severity: "mild", seriousness: "not_serious", outcome: "unknown", causality: "unassessed", narrative: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  // Fix #1: only patients who are already StudySubjects of this study can
  // have a safety case recorded against them -- the backend enforces this
  // too, but offering the full patient list here would just invite a 400.
  const eligiblePatients = useMemo(
    () => subjects.map((s) => ({ id: s.patient_id, name: s.patient_name })),
    [subjects]
  );

  const load = () => {
    setLoading(true);
    api.getSafetyDashboard(studyId).then((r) => setDash(r.data)).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [studyId]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.patient_id) { setErr("Select a patient."); return; }
    if (!form.event_term.trim()) { setErr("Describe the event."); return; }
    setBusy(true); setErr(null);
    const payload = {
      study_id: studyId,
      site_id: form.site_id ? Number(form.site_id) : null,
      patient_id: Number(form.patient_id),
      event_term: form.event_term,
      event_date: form.event_date || null,
      severity: form.severity,
      seriousness: form.seriousness,
      outcome: form.outcome,
      causality: form.causality,
      narrative: form.narrative || null,
    };
    try {
      const isSerious = form.seriousness !== "not_serious";
      const res = isSerious ? await api.createSAE(payload) : await api.createAdverseEvent(payload);
      if (res.data?.error) { setErr(res.data.error); return; }
      setForm({
        site_id: "", patient_id: "", event_term: "", event_date: "",
        severity: "mild", seriousness: "not_serious", outcome: "unknown", causality: "unassessed", narrative: "",
      });
      load();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || e2?.response?.data?.error || "Could not record case.");
    } finally { setBusy(false); }
  };

  const advanceStatus = async (caseId, currentStatus) => {
    const idx = SAFETY_STATUS_FLOW.indexOf(currentStatus);
    const next = SAFETY_STATUS_FLOW[idx + 1];
    if (!next) return;
    await api.updateSafetyCaseStatus(caseId, next);
    load();
  };

  if (loading) return <p className="loading">Loading...</p>;

  return (
    <div>
      {dash && (
        <div className="kpi-grid">
          <GlassCard className="kpi-card">
            <div className="kpi-card-icon">🩹</div>
            <div className="kpi-card-value">{dash.ae_count}</div>
            <div className="kpi-card-label">Adverse Events</div>
          </GlassCard>
          <GlassCard className="kpi-card" glow={dash.sae_count > 0 ? "warning" : undefined}>
            <div className="kpi-card-icon">🚨</div>
            <div className="kpi-card-value">{dash.sae_count}</div>
            <div className="kpi-card-label">Serious Adverse Events</div>
          </GlassCard>
          <GlassCard className="kpi-card">
            <div className="kpi-card-icon">📂</div>
            <div className="kpi-card-value">{dash.open_cases}</div>
            <div className="kpi-card-label">Open Cases</div>
          </GlassCard>
          <GlassCard className="kpi-card" glow={dash.overdue_reports > 0 ? "warning" : undefined}>
            <div className="kpi-card-icon">⏰</div>
            <div className="kpi-card-value">{dash.overdue_reports}</div>
            <div className="kpi-card-label">Overdue Reports</div>
          </GlassCard>
        </div>
      )}
      {dash?.deadline_disclaimer && (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "-6px 0 16px" }}>
          {dash.deadline_disclaimer}
        </p>
      )}

      <GlassCard glow="ai">
        <div className="card-header"><strong>Capture AE / SAE</strong></div>
        <form onSubmit={submit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Patient</label>
              <select value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })}>
                <option value="">Select patient…</option>
                {eligiblePatients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              {eligiblePatients.length === 0 && (
                <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "4px 0 0" }}>
                  No subjects on this study yet — add one on the Subjects tab first.
                </p>
              )}
            </div>
            <div>
              <label>Site (optional)</label>
              <select value={form.site_id} onChange={(e) => setForm({ ...form, site_id: e.target.value })}>
                <option value="">Unspecified</option>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.institution}</option>)}
              </select>
            </div>
          </div>
          <label>Event description</label>
          <textarea rows={2} value={form.event_term} onChange={(e) => setForm({ ...form, event_term: e.target.value })} placeholder="e.g. Moderate rash, resolved with antihistamine" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
            <div>
              <label>Severity</label>
              <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                <option value="mild">mild</option>
                <option value="moderate">moderate</option>
                <option value="severe">severe</option>
              </select>
            </div>
            <div>
              <label>Seriousness</label>
              <select value={form.seriousness} onChange={(e) => setForm({ ...form, seriousness: e.target.value })}>
                <option value="not_serious">Not serious (AE)</option>
                <option value="death">Death</option>
                <option value="life_threatening">Life-threatening</option>
                <option value="hospitalization">Hospitalization</option>
                <option value="disability">Persistent disability</option>
                <option value="other_serious">Other medically serious</option>
              </select>
            </div>
            <div>
              <label>Outcome</label>
              <select value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })}>
                <option value="recovered">recovered</option>
                <option value="recovering">recovering</option>
                <option value="not_recovered">not recovered</option>
                <option value="fatal">fatal</option>
                <option value="unknown">unknown</option>
              </select>
            </div>
            <div>
              <label>Causality</label>
              <select value={form.causality} onChange={(e) => setForm({ ...form, causality: e.target.value })}>
                <option value="unrelated">unrelated</option>
                <option value="unlikely">unlikely</option>
                <option value="possible">possible</option>
                <option value="probable">probable</option>
                <option value="definite">definite</option>
                <option value="unassessed">unassessed</option>
              </select>
            </div>
          </div>
          {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
          <GradientButton variant="primary" type="submit" disabled={busy}>{busy ? "Recording..." : "Record Case"}</GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading"><span className="section-heading-icon">📋</span> Cases ({dash?.total_cases ?? 0})</div>
      {dash && dash.cases.length === 0 && <GlassCard>No AE/SAE cases recorded for this study yet.</GlassCard>}
      {dash && dash.cases.map((c) => {
        const idx = SAFETY_STATUS_FLOW.indexOf(c.status);
        const next = SAFETY_STATUS_FLOW[idx + 1];
        return (
          <GlassCard key={c.id} glow={c.due_status === "overdue" ? "warning" : undefined}>
            <div className="card-header">
              <strong>{c.is_serious ? "🚨 SAE" : "AE"} — {c.event_term}</strong>
              <div style={{ display: "flex", gap: 6 }}>
                {safetyBadge(SAFETY_SEVERITY_BADGE, c.severity)}
                {safetyBadge(SAFETY_STATUS_BADGE, c.status)}
                {c.due_status && safetyBadge(SAFETY_DUE_BADGE, c.due_status)}
              </div>
            </div>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "2px 0" }}>
              {c.patient_name} · {c.site_name || "Site unspecified"} · Event {fmtDateTime(c.event_date)}
            </p>
            <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "2px 0" }}>
              Report due: {fmtDateTime(c.report_due_date)}
            </p>
            {next && (
              <GradientButton variant="secondary" onClick={() => advanceStatus(c.id, c.status)} style={{ marginTop: 6 }}>
                Move to "{next.replace(/_/g, " ")}"
              </GradientButton>
            )}
          </GlassCard>
        );
      })}
    </div>
  );
}
