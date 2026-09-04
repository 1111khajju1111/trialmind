import { Suspense } from "react";
import { useNavigate } from "react-router-dom";
import AgentCoreScene from "./AgentCoreScene.jsx";
import SceneErrorBoundary from "./SceneErrorBoundary.jsx";
import { useScenePerformanceTier } from "../design-system/motion.js";

const SceneFallback = () => (
  <div className="dna-hero-scene-fallback">
    <div className="dna-hero-scene-fallback-orb" />
  </div>
);

// Semantic mapping for the DNA structure, per the change plan: the same
// four nodes the Clinical Intelligence Network already visualizes
// (protocol -> patients -> evidence -> human review, around a core),
// described here as a static editorial legend next to the frame.
const REGIONS = [
  { key: "protocol", label: "01 PROTOCOL", kind: "Input", copy: "Trial protocol and eligibility criteria." },
  { key: "patients", label: "02 PATIENTS", kind: "Input", copy: "Patient population and screening stream." },
  { key: "evidence", label: "03 EVIDENCE", kind: "Reasoning", copy: "RAG sources and supporting evidence." },
  { key: "review", label: "04 HUMAN REVIEW", kind: "Decision", copy: "Candidates requiring human judgment." },
];

/**
 * Dashboard command center. No usePointerParallax / useScrollParallax
 * here at all, by design — a dashboard needs stable spatial orientation,
 * not a decorative effect that reacts to pointer position or scroll
 * offset. The DNA network itself has its own continuous, anchored motion
 * (a slow self-rotation, pulses, particle flow along strands — see
 * AgentCoreScene.jsx's `HelixSpin`), which is the "subtle internal
 * motion" the brief asks for. There is no dark frame around it: the
 * <canvas> has no background color, so it sits directly on this page's
 * light/off-white canvas. `strip` is the live 5-KPI system strip.
 */
export default function DNADashboardHero({ strip }) {
  const navigate = useNavigate();
  const perfTier = useScenePerformanceTier(); // full | reduced | static

  return (
    <section className="dna-hero">
      <div className="dna-hero-copy">
        <div className="dna-hero-eyebrow">TRIALMIND / CLINICAL INTELLIGENCE</div>
        <h1 className="dna-hero-title">
          One system.<br />Four moves.
        </h1>
        <p className="dna-hero-sub">
          Protocol in, patients matched, evidence retrieved, a human decides.
          The structure below is TrialMind's own pipeline — not a diagram of it.
        </p>
        <div className="dna-hero-actions">
          <button className="dna-hero-primary" onClick={() => navigate("/trialmind")}>
            Start Screening
          </button>
          <button className="dna-hero-secondary" onClick={() => navigate("/audit")}>
            View Audit Trail
          </button>
        </div>
      </div>

      <div className="dna-hero-visual">
        <div className="dna-hero-frame">
          <SceneErrorBoundary fallback={<SceneFallback />}>
            {perfTier === "static" ? (
              <SceneFallback />
            ) : (
              <Suspense fallback={<SceneFallback />}>
                <AgentCoreScene />
              </Suspense>
            )}
          </SceneErrorBoundary>
          <div className="dna-hero-frame-label">
            <strong>AGENT CORE</strong>
            <span>READY · 03 TOOLS · RAG ONLINE</span>
          </div>
        </div>

        <ul className="dna-hero-legend">
          {REGIONS.map((r) => (
            <li key={r.key} className="dna-hero-legend-item">
              <span className="dna-hero-legend-label">{r.label}</span>
              <span className="dna-hero-legend-kind">{r.kind}</span>
              <span className="dna-hero-legend-copy">{r.copy}</span>
            </li>
          ))}
        </ul>
      </div>

      {strip && strip.length > 0 && (
        <div className="dna-hero-strip">
          {strip.slice(0, 5).map((item) => (
            <div className="dna-hero-strip-item" key={item.label}>
              <div className="dna-hero-strip-value">{item.value}</div>
              <div className="dna-hero-strip-label">{item.label}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
