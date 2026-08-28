import { useEffect, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";
import KPIGrid from "../components/dashboard/KPIGrid.jsx";

const SEVERITIES = ["mild", "moderate", "severe"];
const SERIOUSNESS_OPTIONS = [
  { value: "not_serious", label: "Not serious (AE)" },
  { value: "death", label: "Death" },
  { value: "life_threatening", label: "Life-threatening" },
  { value: "hospitalization", label: "Hospitalization" },
  { value: "disability", label: "Persistent disability" },
  { value: "other_serious", label: "Other medically serious" },
];
const OUTCOMES = ["recovered", "recovering", "not_recovered", "fatal", "unknown"];
const CAUSALITIES = ["unrelated", "unlikely", "possible", "probable", "definite", "unassessed"];
const STATUS_FLOW = ["draft", "under_review", "reported", "closed"];

const STATUS_BADGE = { draft: "normal", under_review: "high", reported: "approved", closed: "normal" };
const SEVERITY_BADGE = { mild: "normal", moderate: "high", severe: "rejected" };
const DUE_BADGE = { overdue: "rejected", approaching: "high", on_track: "approved" };

function badge(map, value, fallback = "normal") {
  return <span className={`badge ${map[value] || fallback}`}>{(value || "").replace(/_/g, " ")}</span>;
}

function fmtDateTime(d) {
  return d ? new Date(d).toLocaleString() : "—";
}

export default function Safety() {
  const [studies, setStudies] = useState([]);
  const [studyId, setStudyId] = useState("");
  const [sites, setSites] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [dash, setDash] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAll = () => {
    setLoading(true);
    api.getStudies()
      .then((s) => setStudies(s.data))
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadAll(); }, []);

  const loadDashboard = (sid) => {
    api.getSafetyDashboard(sid || undefined).then((r) => setDash(r.data)).catch(() => {});
  };

  useEffect(() => { loadDashboard(studyId); }, [studyId]);

  useEffect(() => {
    if (!studyId) { setSites([]); setSubjects([]); return; }
    api.getSites(Number(studyId)).then((r) => setSites(r.data)).catch(() => setSites([]));
    // Fix #1: AE/SAE capture is only meaningful (and only accepted by the
    // backend) for patients already tracked as StudySubjects on this study.
    api.getStudySubjects(Number(studyId)).then((r) => setSubjects(r.data)).catch(() => setSubjects([]));
  }, [studyId]);

  if (loading) return <p className="loading">Loading...</p>;
  if (error) return <div className="alert-box">{error}</div>;

  return (
    <div>
      <h1>Pharmacovigilance — AE / SAE Safety</h1>
      <p className="subtitle">
        Capture adverse events and serious adverse events, track them through Draft → Under
        Review → Reported → Closed, and monitor regulatory-reporting deadlines.
      </p>

      <div style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 16, flexWrap: "wrap" }}>
        <div style={{ minWidth: 260 }}>
          <label>Filter by study</label>
          <select value={studyId} onChange={(e) => setStudyId(e.target.value)}>
            <option value="">All studies (portfolio-wide)</option>
            {studies.map((s) => (
              <option key={s.id} value={s.id}>{s.study_code} — {s.title}</option>
            ))}
          </select>
        </div>
      </div>

      {dash && (
        <>
          <KPIGrid
            items={[
              { icon: "\u{1FA79}", label: "Adverse Events (AE)", value: dash.ae_count },
              {
                icon: "\u{1F6A8}", label: "Serious Adverse Events (SAE)", value: dash.sae_count,
                glow: dash.sae_count > 0 ? "warning" : undefined,
              },
              { icon: "\u{1F4C2}", label: "Open Cases", value: dash.open_cases },
              {
                icon: "\u23F0", label: "Overdue Reports", value: dash.overdue_reports,
                glow: dash.overdue_reports > 0 ? "warning" : undefined,
              },
              {
                icon: "\u23F3", label: "Approaching Due", value: dash.approaching_due_reports,
                glow: dash.approaching_due_reports > 0 ? "warning" : undefined,
              },
            ]}
          />
          {dash.deadline_disclaimer && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "-6px 0 16px" }}>
              {dash.deadline_disclaimer}
            </p>
          )}
          {Object.keys(dash.monthly_trend || {}).length > 0 && (
            <>
              <div className="section-heading"><span className="section-heading-icon">📈</span> Monthly Trend</div>
              <GlassCard>
                <div style={{ display: "flex", gap: 16, alignItems: "flex-end", height: 90 }}>
                  {Object.entries(dash.monthly_trend).map(([month, count]) => {
                    const max = Math.max(1, ...Object.values(dash.monthly_trend));
                    return (
                      <div key={month} style={{ textAlign: "center", flex: 1 }}>
                        <div
                          style={{
                            height: `${Math.max(6, (count / max) * 70)}px`,
                            background: "var(--gradient-warning)",
                            borderRadius: 4,
                            marginBottom: 6,
                          }}
                        />
                        <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{month}</div>
                        <div style={{ fontSize: 12, fontWeight: 700 }}>{count}</div>
                      </div>
                    );
                  })}
                </div>
              </GlassCard>
            </>
          )}
        </>
      )}

      <CaptureForm
        studyId={studyId}
        sites={sites}
        subjects={subjects}
        onCreated={() => loadDashboard(studyId)}
      />

      <div className="section-heading">
        <span className="section-heading-icon">📋</span> Cases {dash ? `(${dash.total_cases})` : ""}
      </div>
      {dash && dash.cases.length === 0 && <GlassCard>No AE/SAE cases recorded yet.</GlassCard>}
      {dash && dash.cases.map((c) => (
        <CaseCard key={c.id} caseData={c} onChange={() => loadDashboard(studyId)} />
      ))}
    </div>
  );
}

function CaptureForm({ studyId, sites, subjects, onCreated }) {
  const [form, setForm] = useState({
    site_id: "", patient_id: "",
    event_term: "", event_date: "", severity: "mild", seriousness: "not_serious",
    outcome: "unknown", causality: "unassessed", narrative: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [ok, setOk] = useState(null);

  // Fix #1: only patients already tracked as StudySubjects on the selected
  // study can have a safety case recorded -- the backend enforces this,
  // this just keeps the form from offering choices that would 400.
  const eligiblePatients = subjects.map((s) => ({ id: s.patient_id, name: s.patient_name }));

  useEffect(() => {
    setForm((f) => ({ ...f, site_id: "", patient_id: "" }));
  }, [studyId]);

  const submit = async (e) => {
    e.preventDefault();
    if (!studyId) { setErr("Select a study above first."); return; }
    if (!form.patient_id) { setErr("Select a patient."); return; }
    if (!form.event_term.trim()) { setErr("Describe the event."); return; }
    setBusy(true); setErr(null); setOk(null);
    const payload = {
      study_id: Number(studyId),
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
      setOk(`${isSerious ? "SAE" : "AE"} recorded. Report due ${new Date(res.data.report_due_date).toLocaleString()}.`);
      setForm((f) => ({
        ...f, event_term: "", event_date: "", narrative: "",
        severity: "mild", seriousness: "not_serious", outcome: "unknown", causality: "unassessed",
      }));
      onCreated();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || e2?.response?.data?.error || "Could not record case.");
    } finally { setBusy(false); }
  };

  if (!studyId) {
    return (
      <GlassCard glow="ai">
        <div className="card-header"><strong>Capture AE / SAE</strong></div>
        <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Select a study above to capture a case against one of its subjects.
        </p>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="ai">
      <div className="card-header"><strong>Capture AE / SAE</strong></div>
      <form onSubmit={submit}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <label>Patient (must be a subject of this study)</label>
            <select value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })}>
              <option value="">Select patient…</option>
              {eligiblePatients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            {eligiblePatients.length === 0 && (
              <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "4px 0 0" }}>
                No subjects on this study yet — add one from the study's Subjects tab first.
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
          <div>
            <label>Event date</label>
            <input type="datetime-local" value={form.event_date} onChange={(e) => setForm({ ...form, event_date: e.target.value })} />
          </div>
        </div>

        <label>Event description</label>
        <textarea rows={2} value={form.event_term} onChange={(e) => setForm({ ...form, event_term: e.target.value })} placeholder="e.g. Severe hypoglycemia requiring hospital admission" />

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
          <div>
            <label>Severity</label>
            <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label>Seriousness</label>
            <select value={form.seriousness} onChange={(e) => setForm({ ...form, seriousness: e.target.value })}>
              {SERIOUSNESS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label>Outcome</label>
            <select value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })}>
              {OUTCOMES.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div>
            <label>Causality</label>
            <select value={form.causality} onChange={(e) => setForm({ ...form, causality: e.target.value })}>
              {CAUSALITIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <label>Narrative (optional)</label>
        <textarea rows={2} value={form.narrative} onChange={(e) => setForm({ ...form, narrative: e.target.value })} />

        {form.seriousness !== "not_serious" && (
          <p style={{ fontSize: 12, color: "var(--accent-amber)", margin: "4px 0" }}>
            This will be recorded as a Serious Adverse Event (SAE).
          </p>
        )}
        {err && <div className="alert-box" style={{ marginTop: 8 }}>{err}</div>}
        {ok && <div className="alert-box" style={{ marginTop: 8, borderColor: "var(--accent-emerald)" }}>{ok}</div>}
        <GradientButton variant="primary" type="submit" disabled={busy}>
          {busy ? "Recording..." : "Record Case"}
        </GradientButton>
      </form>
    </GlassCard>
  );
}

function CaseCard({ caseData: c, onChange }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const currentIdx = STATUS_FLOW.indexOf(c.status);
  const nextStatus = STATUS_FLOW[currentIdx + 1];

  const advance = async () => {
    if (!nextStatus) return;
    setBusy(true); setErr(null);
    try {
      await api.updateSafetyCaseStatus(c.id, nextStatus);
      onChange();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Could not update status.");
    } finally { setBusy(false); }
  };

  return (
    <GlassCard glow={c.due_status === "overdue" ? "warning" : undefined}>
      <div className="card-header">
        <strong>{c.is_serious ? "🚨 SAE" : "AE"} — {c.event_term}</strong>
        <div style={{ display: "flex", gap: 6 }}>
          {badge(SEVERITY_BADGE, c.severity)}
          {badge(STATUS_BADGE, c.status)}
          {c.due_status && badge(DUE_BADGE, c.due_status)}
        </div>
      </div>
      <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "4px 0" }}>
        {c.patient_name} · {c.site_name || "Site unspecified"} · Event {fmtDateTime(c.event_date)}
      </p>
      <p style={{ fontSize: 12.5, margin: "4px 0" }}>
        Seriousness: <strong>{c.seriousness.replace(/_/g, " ")}</strong> · Outcome:{" "}
        <strong>{c.outcome.replace(/_/g, " ")}</strong> · Causality: <strong>{c.causality}</strong>
      </p>
      {c.narrative && <p style={{ fontSize: 13, margin: "4px 0" }}>{c.narrative}</p>}
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0" }}>
        Report due: {fmtDateTime(c.report_due_date)}
        {c.reported_date ? ` · Reported: ${fmtDateTime(c.reported_date)}` : ""}
      </p>
      {err && <div className="alert-box" style={{ marginTop: 6 }}>{err}</div>}
      {nextStatus && (
        <GradientButton variant="secondary" disabled={busy} onClick={advance} style={{ marginTop: 6 }}>
          {busy ? "Updating..." : `Move to "${nextStatus.replace(/_/g, " ")}"`}
        </GradientButton>
      )}
    </GlassCard>
  );
}
