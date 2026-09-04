import { useEffect, useMemo, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import ActionTimeline from "../components/ActionTimeline.jsx";
import { IconCompass, IconFolder } from "../design-system/icons.jsx";

export default function AuditTrail() {
  const [runs, setRuns] = useState([]);
  const [trials, setTrials] = useState([]);
  const [log, setLog] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.getRuns(), api.getTrials(), api.getApprovalLog()])
      .then(([r, t, l]) => {
        setRuns(r.data);
        setTrials(t.data);
        setLog(l.data);
        if (r.data.length) selectRun(r.data[0].run_id);
      })
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  }, []);

  const trialName = (id) => trials.find((t) => t.id === id)?.name || `Trial #${id}`;

  const selectRun = (runId) => {
    setSelectedRun(runId);
    setTimelineLoading(true);
    api.getTimeline(runId)
      .then((res) => setTimeline(res.data))
      .catch(() => setError("Could not load timeline for this run."))
      .finally(() => setTimelineLoading(false));
  };

  const runIsRunning = useMemo(() => {
    const terminal = new Set(["run_completed", "run_timeout", "agent_error", "persistence_failed"]);
    return timeline.length > 0 && !timeline.some((s) => terminal.has(s.step_name));
  }, [timeline]);

  return (
    <div>
      <h1>Activity &amp; Audit Trail</h1>
      <p className="subtitle">
        Every agent run and every human approval decision, in order — the
        complete record for tracing how a result was reached.
      </p>

      {error && <div className="alert-box">{error}</div>}
      {loading && <p className="loading">Loading...</p>}

      {!loading && (
        <>
          <div className="section-heading">
            <span className="section-heading-icon"><IconCompass /></span> Agent Runs
          </div>

          {runs.length === 0 && <GlassCard>No agent runs yet. Run the matching agent from Trial Matching.</GlassCard>}

          <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 320px) 1fr", gap: 16, alignItems: "start" }}>
            {runs.length > 0 && (
              <div>
                {runs.map((r) => (
                  <GlassCard
                    key={r.run_id}
                    glow={r.run_id === selectedRun ? "ai" : undefined}
                    onClick={() => selectRun(r.run_id)}
                    style={{
                      cursor: "pointer",
                      outline: r.run_id === selectedRun ? "1px solid var(--accent-violet)" : "none",
                    }}
                  >
                    <div className="card-header">
                      <strong style={{ fontSize: 13 }}>{trialName(r.trial_id)}</strong>
                    </div>
                    <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: 0 }}>
                      run {r.run_id} · {r.timestamp ? new Date(r.timestamp).toLocaleString() : "unknown time"}
                    </p>
                  </GlassCard>
                ))}
              </div>
            )}

            {runs.length > 0 && (
              <div>
                {timelineLoading ? (
                  <p className="loading">Loading timeline...</p>
                ) : (
                  <ActionTimeline steps={timeline} running={runIsRunning} />
                )}
              </div>
            )}
          </div>

          <div className="section-heading" style={{ marginTop: 28 }}>
            <span className="section-heading-icon"><IconFolder /></span> Approval Log
          </div>

          {log.length === 0 && (
            <GlassCard>No approvals or rejections yet.</GlassCard>
          )}

          {log.map((entry) => (
            <GlassCard key={entry.id}>
              <div className="card-header">
                <strong>{entry.module.replace("_", " ")}</strong>
                <span className={`badge ${entry.action}`}>{entry.action}</span>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)" }}>
                Record #{entry.record_id} · {entry.actor} · {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "unknown time"}
              </p>
            </GlassCard>
          ))}
        </>
      )}
    </div>
  );
}
