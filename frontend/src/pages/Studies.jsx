import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";

const STATUS_BADGE = {
  planning: "normal",
  active: "approved",
  paused: "high",
  completed: "approved",
  terminated: "rejected",
};

const EMPTY_FORM = {
  study_code: "",
  title: "",
  phase: "Phase III",
  intervention: "",
  principal_investigator: "",
  target_enrollment: 100,
};

export default function Studies() {
  const [studies, setStudies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

  const load = () => {
    setLoading(true);
    api.getStudies()
      .then((res) => setStudies(res.data))
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api.createStudy({
        ...form,
        target_enrollment: Number(form.target_enrollment) || 0,
      });
      setForm(EMPTY_FORM);
      load();
    } catch (err) {
      setCreateError(err?.response?.data?.detail || "Could not create study.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <h1>Studies</h1>
      <p className="subtitle">
        The CTMS core: every study, its phase and PI, and where recruitment
        stands against target. Open a study to manage its sites, subjects,
        milestones, deviations and monitoring visits.
      </p>

      {error && <div className="alert-box">{error}</div>}

      <GlassCard glow="ai">
        <div className="card-header">
          <strong>Create Study</strong>
        </div>
        <form onSubmit={submit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Study code</label>
              <input
                required
                placeholder="STUDY-002"
                value={form.study_code}
                onChange={(e) => setForm({ ...form, study_code: e.target.value })}
              />
            </div>
            <div>
              <label>Phase</label>
              <select value={form.phase} onChange={(e) => setForm({ ...form, phase: e.target.value })}>
                {["Phase I", "Phase II", "Phase III", "Phase IV"].map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>
          <label>Title</label>
          <input
            required
            placeholder="Study title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label>Intervention</label>
              <input
                value={form.intervention}
                onChange={(e) => setForm({ ...form, intervention: e.target.value })}
              />
            </div>
            <div>
              <label>Principal investigator</label>
              <input
                value={form.principal_investigator}
                onChange={(e) => setForm({ ...form, principal_investigator: e.target.value })}
              />
            </div>
          </div>
          <label>Target enrollment</label>
          <input
            type="number"
            min="0"
            value={form.target_enrollment}
            onChange={(e) => setForm({ ...form, target_enrollment: e.target.value })}
          />
          {createError && <div className="alert-box" style={{ marginTop: 8 }}>{createError}</div>}
          <GradientButton variant="primary" type="submit" disabled={creating}>
            {creating ? "Creating..." : "Create Study"}
          </GradientButton>
        </form>
      </GlassCard>

      <div className="section-heading">
        <span className="section-heading-icon">🏥</span> All Studies
      </div>

      {loading && <p className="loading">Loading...</p>}
      {!loading && studies.length === 0 && <GlassCard>No studies yet. Create one above.</GlassCard>}

      <div className="agent-grid" style={{ marginTop: 16 }}>
        {studies.map((s) => {
          const pct = s.target_enrollment > 0
            ? Math.min(100, Math.round((s.enrolled_count / s.target_enrollment) * 100))
            : 0;
          return (
            <Link key={s.id} to={`/studies/${s.id}`} style={{ textDecoration: "none", color: "inherit" }}>
              <GlassCard>
                <div className="card-header">
                  <strong>{s.study_code}</strong>
                  <span className={`badge ${STATUS_BADGE[s.status] || "normal"}`}>{s.status}</span>
                </div>
                <p style={{ fontSize: 13, fontWeight: 600, margin: "2px 0 6px" }}>{s.title}</p>
                <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "0 0 8px" }}>
                  {s.phase || "Phase n/a"} · PI: {s.principal_investigator || "unassigned"}
                </p>
                <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
                  Enrolled {s.enrolled_count} / {s.target_enrollment} ({pct}%)
                </p>
              </GlassCard>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
