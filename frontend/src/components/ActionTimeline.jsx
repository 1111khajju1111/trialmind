import { IconCross } from "./../design-system/icons.jsx";

const STEP_LABELS = {
  run_started: "Agent started",
  protocol_loaded: "Trial protocol loaded",
  search_patients: "Patient search",
  evaluate_eligibility: "Eligibility check completed",
  retrieve_evidence: "Evidence retrieval requested",
  evidence_retrieved: "Evidence retrieved",
  evidence_not_found: "No reliable evidence found",
  tool_error: "Tool error",
  agent_error: "Agent error",
  ranking_completed: "Candidate ranking completed",
  run_completed: "Run completed — human review required",
  persistence_failed: "Failed to save results",
  run_timeout: "Stopped (max steps reached)",
};

const ERROR_STEPS = new Set(["tool_error", "agent_error", "run_timeout", "evidence_not_found", "persistence_failed"]);
const TERMINAL_STEPS = new Set(["run_completed", "run_timeout", "agent_error", "persistence_failed"]);

function fmtTime(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour12: false });
  } catch {
    return null;
  }
}

export default function ActionTimeline({ steps, running }) {
  if (!steps || steps.length === 0) {
    if (running) {
      return (
        <div className="card agent-run-card">
          <div className="agent-run-header">
            <strong>Agent Run</strong>
          </div>
          <p className="loading" style={{ marginTop: 8 }}>Waiting for agent to start...</p>
        </div>
      );
    }
    return null;
  }

  const lastStep = steps[steps.length - 1];
  const runIdShort = lastStep ? "" : "";

  return (
    <div className="card agent-run-card">
      <div className="agent-run-header">
        <strong>Agent Run</strong>
        {!TERMINAL_STEPS.has(lastStep?.step_name) && running && (
          <span className="agent-run-live-dot" aria-hidden="true">●</span>
        )}
      </div>
      <div style={{ marginTop: 10 }}>
        {steps.map((s, i) => {
          const isError = ERROR_STEPS.has(s.step_name);
          const isLast = i === steps.length - 1;
          const isActive = isLast && running && !TERMINAL_STEPS.has(s.step_name);
          return (
            <div key={s.id} className={`agent-run-step ${isActive ? "is-active" : ""}`}>
              <div
                className={`agent-run-step-dot ${isError ? "is-error" : ""} ${isActive ? "is-pulsing" : ""}`}
              >
                {isError ? <IconCross /> : i + 1}
              </div>
              <div className="agent-run-step-body">
                <div className="agent-run-step-title" style={{ color: isError ? "var(--accent-red)" : "inherit" }}>
                  {STEP_LABELS[s.step_name] || s.step_name}
                  {fmtTime(s.timestamp) && (
                    <span className="agent-run-step-time">{fmtTime(s.timestamp)}</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{s.detail}</div>
              </div>
            </div>
          );
        })}
        {running && !TERMINAL_STEPS.has(lastStep?.step_name) && (
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: 32 }}>Agent still working...</div>
        )}
      </div>
    </div>
  );
}
