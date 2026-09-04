import { useEffect, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";
import KPIGrid from "../components/dashboard/KPIGrid.jsx";
import { IconTrend, IconClipboard, IconAlertCircle, IconRadar } from "../design-system/icons.jsx";
import HumanInLoopBadge from "../components/ui/HumanInLoopBadge.jsx";

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
const ACTION_TAKEN_OPTIONS = [
  { value: "dose_not_changed", label: "Dose not changed" },
  { value: "dose_reduced", label: "Dose reduced" },
  { value: "drug_withdrawn", label: "Drug withdrawn" },
  { value: "drug_interrupted", label: "Drug interrupted" },
  { value: "unknown", label: "Unknown" },
];
const STATUS_FLOW = ["draft", "under_review", "reported", "closed"];

const STATUS_BADGE = { draft: "normal", under_review: "high", reported: "approved", closed: "normal" };
const SEVERITY_BADGE = { mild: "normal", moderate: "high", severe: "rejected" };
const DUE_BADGE = { overdue: "rejected", approaching: "high", on_track: "approved" };

// Priority 3(b) -- Safety Signal Engine. open/escalated read as "needs
// attention" (red), under_review as "in progress" (amber), dismissed as
// "resolved, not an issue" (grey) -- distinct from the AE/SAE case-status
// palette above so the two workflows read as visually separate at a glance.
const SIGNAL_STATUS_BADGE = { open: "urgent", under_review: "high", escalated: "rejected", dismissed: "normal" };
const SIGNAL_STATUS_LABEL = {
  open: "Open — needs review", under_review: "Under review",
  escalated: "Escalated", dismissed: "Dismissed",
};

function badge(map, value, fallback = "normal") {
  return <span className={`badge ${map[value] || fallback}`}>{(value || "").replace(/_/g, " ")}</span>;
}

function confidenceBadge(score) {
  const cls = score >= 0.7 ? "urgent" : score >= 0.4 ? "high" : "normal";
  return <span className={`badge ${cls}`}>{Math.round((score || 0) * 100)}% confidence</span>;
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
              <div className="section-heading"><span className="section-heading-icon"><IconTrend /></span> Monthly Trend</div>
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
        <span className="section-heading-icon"><IconClipboard /></span> Cases {dash ? `(${dash.total_cases})` : ""}
      </div>
      {dash && dash.cases.length === 0 && <GlassCard>No AE/SAE cases recorded yet.</GlassCard>}
      {dash && dash.cases.map((c) => (
        <CaseCard key={c.id} caseData={c} onChange={() => loadDashboard(studyId)} />
      ))}

      <SignalEnginePanel studyId={studyId} />
    </div>
  );
}

function CaptureForm({ studyId, sites, subjects, onCreated }) {
  const [form, setForm] = useState({
    site_id: "", patient_id: "",
    event_term: "", event_date: "", severity: "mild", seriousness: "not_serious",
    outcome: "unknown", causality: "unassessed", narrative: "",
    drug: "", batch_number: "", dose: "", route: "", administration_date: "", location: "",
    symptom_onset_date: "", action_taken: "",
  });
  const [showSignalFields, setShowSignalFields] = useState(false);
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
      // Priority 3(b): optional signal-engine inputs. Left null unless the
      // coordinator fills them in -- a case is fully valid AE/SAE data
      // without ever touching these, they just won't be eligible for
      // correlation until drug + batch_number are both known.
      drug: form.drug || null,
      batch_number: form.batch_number || null,
      dose: form.dose || null,
      route: form.route || null,
      administration_date: form.administration_date || null,
      location: form.location || null,
      symptom_onset_date: form.symptom_onset_date || null,
      action_taken: form.action_taken || null,
    };
    try {
      const isSerious = form.seriousness !== "not_serious";
      const res = isSerious ? await api.createSAE(payload) : await api.createAdverseEvent(payload);
      if (res.data?.error) { setErr(res.data.error); return; }
      setOk(`${isSerious ? "SAE" : "AE"} recorded. Report due ${new Date(res.data.report_due_date).toLocaleString()}.`);
      setForm((f) => ({
        ...f, event_term: "", event_date: "", narrative: "",
        severity: "mild", seriousness: "not_serious", outcome: "unknown", causality: "unassessed",
        drug: "", batch_number: "", dose: "", route: "", administration_date: "", location: "",
        symptom_onset_date: "", action_taken: "",
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

        <button
          type="button"
          onClick={() => setShowSignalFields((v) => !v)}
          style={{
            background: "none", border: "none", padding: "6px 0", cursor: "pointer",
            color: "var(--accent-purple, var(--accent-amber))", fontSize: 12.5, fontWeight: 600,
            display: "flex", alignItems: "center", gap: 4,
          }}
        >
          <IconRadar style={{ fontSize: 14 }} />
          {showSignalFields ? "Hide" : "Add"} drug / batch details (enables Safety Signal Engine correlation)
        </button>

        {showSignalFields && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, padding: "4px 0 8px" }}>
            <div>
              <label>Drug</label>
              <input value={form.drug} onChange={(e) => setForm({ ...form, drug: e.target.value })} placeholder="e.g. Metformin" />
            </div>
            <div>
              <label>Batch number</label>
              <input value={form.batch_number} onChange={(e) => setForm({ ...form, batch_number: e.target.value })} placeholder="e.g. BATCH-017" />
            </div>
            <div>
              <label>Dose</label>
              <input value={form.dose} onChange={(e) => setForm({ ...form, dose: e.target.value })} placeholder="e.g. 500mg" />
            </div>
            <div>
              <label>Route</label>
              <input value={form.route} onChange={(e) => setForm({ ...form, route: e.target.value })} placeholder="e.g. Oral, IV" />
            </div>
            <div>
              <label>Administration date/time</label>
              <input type="datetime-local" value={form.administration_date} onChange={(e) => setForm({ ...form, administration_date: e.target.value })} />
            </div>
            <div>
              <label>Location (ward / clinic)</label>
              <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="e.g. Ward B, Site A" />
            </div>
            <div>
              <label>Symptom onset date/time</label>
              <input type="datetime-local" value={form.symptom_onset_date} onChange={(e) => setForm({ ...form, symptom_onset_date: e.target.value })} />
            </div>
            <div>
              <label>Action taken with drug</label>
              <select value={form.action_taken} onChange={(e) => setForm({ ...form, action_taken: e.target.value })}>
                <option value="">— Not specified —</option>
                {ACTION_TAKEN_OPTIONS.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
            </div>
            <p style={{ gridColumn: "1 / -1", fontSize: 11, color: "var(--text-muted)", margin: "2px 0 0" }}>
              Only cases with both drug and batch number set are eligible for signal detection below.
              Onset date lets a reviewer see dose-to-onset latency at a glance.
            </p>
          </div>
        )}

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
        <strong>{c.is_serious && <IconAlertCircle style={{ marginRight: 4, verticalAlign: "-0.15em" }} />}{c.is_serious ? "SAE" : "AE"} — {c.event_term}</strong>
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
      {(c.drug || c.batch_number) && (
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0" }}>
          <IconRadar style={{ marginRight: 4, verticalAlign: "-0.15em" }} />
          {c.drug || "Drug unspecified"} {c.batch_number ? `· Batch ${c.batch_number}` : ""}
          {c.dose ? ` · ${c.dose}` : ""}{c.route ? ` · ${c.route}` : ""}
          {c.location ? ` · ${c.location}` : ""}
          {c.action_taken ? ` · Action: ${c.action_taken.replace(/_/g, " ")}` : ""}
          {c.onset_latency_hours != null ? ` · Onset ${c.onset_latency_hours}h after dosing` : ""}
        </p>
      )}
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

// ---------- Priority 3(b): Safety Signal Engine ----------

function SignalEnginePanel({ studyId }) {
  const [signals, setSignals] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [windowHours, setWindowHours] = useState(6);
  const [minPatients, setMinPatients] = useState(2);
  const [detectBusy, setDetectBusy] = useState(false);
  const [detectErr, setDetectErr] = useState(null);
  const [detectMsg, setDetectMsg] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");

  const loadSignals = () => {
    api.getSafetySignals({ study_id: studyId || undefined, status: statusFilter || undefined })
      .then((r) => setSignals(r.data))
      .catch(() => setSignals([]))
      .finally(() => setLoaded(true));
  };

  useEffect(() => { loadSignals(); }, [studyId, statusFilter]);

  const runDetection = async () => {
    setDetectBusy(true); setDetectErr(null); setDetectMsg(null);
    try {
      const payload = {
        study_id: studyId ? Number(studyId) : null,
        window_hours: Number(windowHours) || 6,
        min_patients: Number(minPatients) || 2,
      };
      const res = await api.detectSafetySignals(payload);
      setDetectMsg(
        res.data.signals_detected > 0
          ? `${res.data.signals_detected} signal(s) open or updated.`
          : "No new signal clusters found with the current thresholds."
      );
      loadSignals();
    } catch (e) {
      setDetectErr(e?.response?.data?.detail || "Could not run signal detection.");
    } finally { setDetectBusy(false); }
  };

  const openCount = signals.filter((s) => s.status === "open").length;
  const reviewCount = signals.filter((s) => s.status === "under_review").length;

  return (
    <>
      <div className="section-heading">
        <span className="section-heading-icon"><IconRadar /></span> Safety Signal Engine
        {loaded ? ` (${signals.length})` : ""}
      </div>
      <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "-4px 0 12px" }}>
        Correlates AE/SAE cases that share a drug + batch number and cluster in time, optionally
        concentrated at one site, into candidate signals for human pharmacovigilance review.
      </p>

      <GlassCard glow={openCount > 0 ? "warning" : undefined} style={{ marginBottom: 16 }}>
        <div className="card-header"><strong>Run Detection</strong></div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ width: 160 }}>
            <label>Time window (hours)</label>
            <input type="number" min="0.5" step="0.5" value={windowHours} onChange={(e) => setWindowHours(e.target.value)} />
          </div>
          <div style={{ width: 160 }}>
            <label>Min. distinct patients</label>
            <input type="number" min="2" step="1" value={minPatients} onChange={(e) => setMinPatients(e.target.value)} />
          </div>
          <GradientButton variant="primary" disabled={detectBusy} onClick={runDetection}>
            {detectBusy ? "Scanning..." : `Run Detection${studyId ? "" : " (all studies)"}`}
          </GradientButton>
        </div>
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "8px 0 0" }}>
          Only recorded cases with both drug and batch number set are scanned. A cluster becomes a
          signal once it spans at least the chosen number of distinct patients within the time window.
        </p>
        {detectErr && <div className="alert-box" style={{ marginTop: 8 }}>{detectErr}</div>}
        {detectMsg && <div className="alert-box" style={{ marginTop: 8, borderColor: "var(--accent-emerald)" }}>{detectMsg}</div>}
      </GlassCard>

      <div style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 12, flexWrap: "wrap" }}>
        <div style={{ minWidth: 220 }}>
          <label>Filter by status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            {Object.entries(SIGNAL_STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        {(openCount > 0 || reviewCount > 0) && (
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "0 0 8px" }}>
            {openCount > 0 && <span>{openCount} awaiting first review</span>}
            {openCount > 0 && reviewCount > 0 && " · "}
            {reviewCount > 0 && <span>{reviewCount} under review</span>}
          </p>
        )}
      </div>

      {loaded && signals.length === 0 && (
        <GlassCard>No safety signals detected yet. Record drug/batch AE/SAE cases and run detection above.</GlassCard>
      )}
      {signals.map((s) => (
        <SignalCard key={s.id} signal={s} onChange={loadSignals} />
      ))}
    </>
  );
}

// Priority 1 SIH improvement: a compact Drug -> Batch -> Cases -> Signal
// flow diagram, so a reviewer sees at a glance how a signal was built up
// from raw case data rather than just reading a confidence percentage.
// Pure inline SVG (no chart library) to stay consistent with the rest of
// this codebase's dependency-light approach (see rag_service.py / safety_
// signals.py docstrings).
function SignalFlowDiagram({ drug, batchNumber, caseCount, patientCount, siteLabel, confidence }) {
  const stageColor =
    confidence >= 0.7 ? "var(--accent-red)" : confidence >= 0.4 ? "var(--accent-amber)" : "var(--accent-blue)";
  const nodes = [
    { label: "Drug", value: drug || "Unspecified" },
    { label: "Batch", value: batchNumber || "Unspecified" },
    { label: `${caseCount} Case${caseCount === 1 ? "" : "s"}`, value: `${patientCount} patient${patientCount === 1 ? "" : "s"}` },
    { label: "Signal", value: siteLabel ? `at ${siteLabel}` : "multi-site" },
  ];
  const w = 640, h = 92, nodeW = 136, nodeH = 56, gap = (w - nodes.length * nodeW) / (nodes.length - 1) + nodeW;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ maxWidth: 640, display: "block", margin: "8px 0" }}>
      {nodes.slice(0, -1).map((_, i) => {
        const x1 = i * gap + nodeW;
        const x2 = (i + 1) * gap;
        const y = h / 2;
        return (
          <g key={`arrow-${i}`}>
            <line x1={x1} y1={y} x2={x2 - 6} y2={y} stroke="var(--text-muted)" strokeWidth="1.5" />
            <polygon points={`${x2 - 6},${y - 4} ${x2},${y} ${x2 - 6},${y + 4}`} fill="var(--text-muted)" />
          </g>
        );
      })}
      {nodes.map((n, i) => {
        const x = i * gap;
        const isLast = i === nodes.length - 1;
        return (
          <g key={n.label} transform={`translate(${x}, ${(h - nodeH) / 2})`}>
            <rect
              width={nodeW} height={nodeH} rx={10}
              fill={isLast ? stageColor : "var(--bg-secondary)"}
              fillOpacity={isLast ? 0.18 : 1}
              stroke={isLast ? stageColor : "var(--text-muted)"}
              strokeWidth={isLast ? 2 : 1}
            />
            <text x={nodeW / 2} y={nodeH / 2 - 6} textAnchor="middle" fontSize="12.5" fontWeight="700" fill="var(--text)">
              {n.label}
            </text>
            <text x={nodeW / 2} y={nodeH / 2 + 12} textAnchor="middle" fontSize="10.5" fill="var(--text-secondary)">
              {n.value.length > 20 ? n.value.slice(0, 19) + "…" : n.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function SignalCard({ signal: s, onChange }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [notes, setNotes] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [cases, setCases] = useState(null);
  const [casesLoading, setCasesLoading] = useState(false);

  const isTerminal = s.status === "escalated" || s.status === "dismissed";

  const changeStatus = async (newStatus) => {
    setBusy(true); setErr(null);
    try {
      await api.updateSafetySignalStatus(s.id, newStatus, notes || undefined);
      onChange();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Could not update signal status.");
    } finally { setBusy(false); }
  };

  const toggleExpand = () => {
    if (!expanded && cases === null) {
      setCasesLoading(true);
      api.getSafetySignal(s.id)
        .then((r) => setCases(r.data.cases || []))
        .catch(() => setCases([]))
        .finally(() => setCasesLoading(false));
    }
    setExpanded((v) => !v);
  };

  return (
    <GlassCard glow={s.status === "open" ? "warning" : undefined} style={{ marginBottom: 12 }}>
      <div className="card-header">
        <strong>
          <IconRadar style={{ marginRight: 4, verticalAlign: "-0.15em" }} />
          {s.drug} — Batch {s.batch_number}
        </strong>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {confidenceBadge(s.confidence_score)}
          {badge(SIGNAL_STATUS_BADGE, s.status, "normal")}
        </div>
      </div>

      <div
        style={{
          display: "inline-flex", alignItems: "center", gap: 6, margin: "2px 0 6px",
          padding: "2px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700,
          letterSpacing: 0.3, textTransform: "uppercase",
          color: "var(--accent-amber)", border: "1px solid var(--accent-amber)",
        }}
      >
        ⚠ Potential Safety Signal — not a confirmed finding
      </div>
      <div style={{ margin: "0 0 6px" }}>
        <HumanInLoopBadge label="Algorithmically detected — a PV officer decides" />
      </div>

      <SignalFlowDiagram
        drug={s.drug} batchNumber={s.batch_number}
        caseCount={s.case_count} patientCount={s.patient_count}
        siteLabel={s.site_name || s.dominant_location} confidence={s.confidence_score}
      />

      <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "4px 0" }}>
        {s.patient_count} patient(s) · {s.case_count} case(s)
        {s.site_name ? ` · concentrated at ${s.site_name}` : ""}
        {s.dominant_location ? ` (${s.dominant_location})` : ""} · window{" "}
        {fmtDateTime(s.window_start)} → {fmtDateTime(s.window_end)}
      </p>

      <div style={{ display: "flex", gap: 16, margin: "6px 0", fontSize: 12, flexWrap: "wrap" }}>
        <span>Symptom similarity: <strong>{Math.round((s.symptom_similarity || 0) * 100)}%</strong></span>
        <span>Site concentration: <strong>{Math.round((s.site_concentration || 0) * 100)}%</strong></span>
        {s.dominant_location && (
          <span>Location concentration: <strong>{Math.round((s.location_concentration || 0) * 100)}% at {s.dominant_location}</strong></span>
        )}
        <span>Severity score: <strong>{Math.round((s.severity_score || 0) * 100)}%</strong></span>
      </div>

      {s.rationale && (
        <p style={{ fontSize: 13, margin: "8px 0", lineHeight: 1.5 }}>{s.rationale}</p>
      )}

      {isTerminal && (
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "6px 0" }}>
          {badge(SIGNAL_STATUS_BADGE, s.status, "normal")}{" "}
          by {s.reviewed_by || "reviewer"} on {fmtDateTime(s.reviewed_at)}
          {s.review_notes ? `: "${s.review_notes}"` : ""}
        </p>
      )}

      <button
        type="button"
        onClick={toggleExpand}
        style={{
          background: "none", border: "none", padding: "4px 0", cursor: "pointer",
          color: "var(--text-secondary)", fontSize: 12, textDecoration: "underline",
        }}
      >
        {expanded ? "Hide" : "View"} evidence (the cases behind this signal)
      </button>
      {expanded && (
        <div style={{ margin: "6px 0 4px", display: "flex", flexDirection: "column", gap: 6 }}>
          {casesLoading && <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading evidence…</p>}
          {cases && cases.length === 0 && <p style={{ fontSize: 12, color: "var(--text-muted)" }}>No case detail available.</p>}
          {cases && cases.map((c) => (
            <div key={c.id} style={{ fontSize: 12, padding: "6px 8px", background: "var(--bg-secondary)", borderRadius: 6 }}>
              <strong>{c.is_serious ? "SAE" : "AE"}</strong> — {c.event_term} · {c.patient_name} ·{" "}
              {fmtDateTime(c.event_date)} {c.dose ? `· ${c.dose}` : ""} {c.route ? `· ${c.route}` : ""}
              {c.location ? ` · ${c.location}` : ""}
              {c.onset_latency_hours != null ? ` · onset ${c.onset_latency_hours}h post-dose` : ""}
              {c.action_taken ? ` · action: ${c.action_taken.replace(/_/g, " ")}` : ""}
            </div>
          ))}
        </div>
      )}

      {!isTerminal && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border-color, rgba(255,255,255,0.08))" }}>
          {s.status === "under_review" && (
            <textarea
              rows={2}
              placeholder="Review notes (optional) — recorded with the escalate/dismiss decision"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              style={{ marginBottom: 8 }}
            />
          )}
          {err && <div className="alert-box" style={{ marginBottom: 8 }}>{err}</div>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {s.status === "open" && (
              <GradientButton variant="secondary" disabled={busy} onClick={() => changeStatus("under_review")}>
                {busy ? "Updating..." : "Mark Under Review"}
              </GradientButton>
            )}
            {s.status === "under_review" && (
              <>
                <GradientButton variant="danger" disabled={busy} onClick={() => changeStatus("escalated")}>
                  {busy ? "Updating..." : "Escalate for Investigation"}
                </GradientButton>
                <GradientButton variant="secondary" disabled={busy} onClick={() => changeStatus("dismissed")}>
                  {busy ? "Updating..." : "Dismiss as Noise"}
                </GradientButton>
              </>
            )}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
