import { Suspense } from "react";
import AgentCoreScene from "./AgentCoreScene.jsx";
import SceneErrorBoundary from "./SceneErrorBoundary.jsx";
import { useScenePerformanceTier } from "../design-system/motion.js";

const SceneFallback = () => (
  <div className="hero-3d-scene-fallback">
    <div className="hero-3d-scene-fallback-orb" />
  </div>
);

const STAGES = ["protocol", "patients", "evidence", "review"];

// Maps a confirmed timeline step_name to how far the pipeline has actually
// progressed. `passedThrough` = index of the last stage fully confirmed
// done by a real backend event (-1 = nothing confirmed yet). `activeStage`
// (only meaningful while `running`) = the stage currently in flight.
// Nothing is ever marked "passed" without a real step_name behind it --
// `running` alone only ever advances the *active* pointer, never the
// passed one, which is what the previous version got wrong.
const STAGE_ACTIVE = {
  run_started: 0,
  search_patients: 1,
  evaluate_eligibility: 1,
  retrieve_evidence: 2,
  ranking_completed: 3,
};
const STAGE_PASSED_THROUGH = {
  protocol_loaded: 0,
  search_patients: 0,
  evaluate_eligibility: 0,
  retrieve_evidence: 1,
  evidence_retrieved: 2,
  evidence_not_found: 2,
  ranking_completed: 2,
  run_completed: 3,
  persistence_failed: 2,
};

function pipelineStageStates({ lastStep, running, hasError }) {
  const passedThrough = STAGE_PASSED_THROUGH[lastStep] ?? -1;
  const activeStage = running
    ? STAGE_ACTIVE[lastStep] ?? Math.min(passedThrough + 1, STAGES.length - 1)
    : null;

  return STAGES.map((_, i) => {
    if (i <= passedThrough) return "passed";
    if (i === activeStage) return hasError ? "error" : "active";
    return "pending";
  });
}

const stageClass = (state) =>
  state === "passed" ? "pipeline-step is-passed"
  : state === "active" ? "pipeline-step is-active"
  : state === "error" ? "pipeline-step is-error"
  : "pipeline-step";

/**
 * TrialMind flagship console — built on the same hero-3d classes as the
 * former homepage hero, so /trialmind reads as the same product
 * experience rather than a second, conventionally-laid-out screen. The
 * Agent Core and system-strip pattern are identical; only the content is
 * specific to a live run (current study, live pipeline state, the
 * primary RUN action).
 *
 * Igloo-inspired pass: operational parallax removed here on purpose —
 * this is a live operational console, not the marketing/landing
 * experience, so it stays spatially stable like the dashboard. Pointer/
 * scroll parallax (design-system/motion.js) is reserved for a future
 * marketing/landing surface only.
 */
export default function TrialMindConsole({
  lastStep,
  pipelineStep,
  running,
  hasError,
  justStarted,
  sceneStatusLabel,
  sceneStepLabel,
  currentTrial,
  patientCount,
  matchCount,
  confidencePct,
  onRun,
  canRun,
  onToggleUpload,
  showUpload,
}) {
  const perfTier = useScenePerformanceTier(); // full | reduced | static

  const statusClass = hasError ? "is-error" : !running && !lastStep ? "is-idle" : "";
  const [protocolState, patientsState, evidenceState, reviewState] =
    pipelineStageStates({ lastStep: pipelineStep ?? lastStep, running, hasError });

  return (
    <section className="hero-3d hero-3d-console">
      <div className="hero-3d-main">
        <div className="hero-3d-copy">
          <div className="hero-3d-eyebrow">TRIALMIND / RECRUITMENT</div>
          <h1 className="hero-3d-title">
            Screen. Match.<br />
            <span>Explain.</span>
          </h1>
          <p className="hero-3d-sub">
            {currentTrial
              ? `${currentTrial.condition} — matching against the full patient directory. Deterministic rules decide; the agent retrieves the evidence behind every call.`
              : "Select a trial protocol to begin. Deterministic rules decide eligibility; the agent retrieves the evidence behind every call."}
          </p>

          <div className={`hero-3d-console-status ${statusClass}`}>
            <span className="hero-3d-console-status-dot" />
            {sceneStatusLabel} · {sceneStepLabel}
          </div>

          <div className="hero-3d-console-pipeline">
            <span className={stageClass(protocolState)}>PROTOCOL</span>
            <span className="pipeline-arrow">→</span>
            <span className={stageClass(patientsState)}>PATIENTS</span>
            <span className="pipeline-arrow">→</span>
            <span className={stageClass(evidenceState)}>EVIDENCE</span>
            <span className="pipeline-arrow">→</span>
            <span className={stageClass(reviewState)}>HUMAN REVIEW</span>
          </div>

          <div className="hero-3d-actions">
            <button className="hero-3d-primary" onClick={onRun} disabled={running || !canRun}>
              {running ? "Running…" : "Run Matching Agent"}
            </button>
            <button className="hero-3d-tertiary" onClick={onToggleUpload} disabled={running}>
              {showUpload ? "Cancel" : "+ Add Trial Protocol"}
            </button>
          </div>
          <div className="hero-3d-micro">SYNTHETIC DATA · HUMAN-IN-THE-LOOP · AUDITABLE WORKFLOW</div>
        </div>

        <div className={`hero-3d-scene ${justStarted ? "is-waking" : ""}`}>
          <SceneErrorBoundary fallback={<SceneFallback />}>
            {perfTier === "static" ? (
              <SceneFallback />
            ) : (
              <Suspense fallback={<SceneFallback />}>
                <AgentCoreScene lastStep={lastStep} running={running} hasError={hasError} />
              </Suspense>
            )}
          </SceneErrorBoundary>
          <div className="hero-3d-scene-label">
            <strong>AGENT CORE</strong>
            <span>{running ? "PROCESSING" : "READY"} · 03 TOOLS · RAG ONLINE</span>
          </div>
        </div>
      </div>

      <div className="hero-strip">
        <div className="hero-strip-item">
          <div className="hero-strip-value">{currentTrial ? currentTrial.name : "—"}</div>
          <div className="hero-strip-label">Current Study</div>
        </div>
        <div className="hero-strip-item">
          <div className="hero-strip-value">{patientCount}</div>
          <div className="hero-strip-label">Patients In Directory</div>
        </div>
        <div className="hero-strip-item">
          <div className="hero-strip-value">{matchCount}</div>
          <div className="hero-strip-label">Candidates Matched</div>
        </div>
        <div className="hero-strip-item">
          <div className="hero-strip-value">{confidencePct}%</div>
          <div className="hero-strip-label">Machine-Checkable</div>
        </div>
      </div>
    </section>
  );
}
