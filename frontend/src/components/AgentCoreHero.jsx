import { Suspense } from "react";
import { useNavigate } from "react-router-dom";
import AgentCoreScene from "./AgentCoreScene.jsx";
import SceneErrorBoundary from "./SceneErrorBoundary.jsx";
import { usePointerParallax, useScrollParallax, useScenePerformanceTier } from "../design-system/motion.js";

const SceneFallback = () => (
  <div className="hero-3d-scene-fallback">
    <div className="hero-3d-scene-fallback-orb" />
  </div>
);

/**
 * P0.2 Command hero — the one spectacular focal moment. Two parallax
 * systems run at once, both scoped to this section only:
 *  - pointer depth: foreground copy / eyebrow shift most, the 3D scene
 *    frame shifts a little, the ambient background barely moves at all
 *    (`data-depth="fg|mid|bg"`, see design-system/motion.js).
 *  - scroll depth: as the hero scrolls past, the background glow drifts
 *    slowest, the Agent Core scene at a medium speed, the kinetic
 *    headline fastest (`data-scroll-speed`) — the layered-depth read the
 *    brief calls "spatial storytelling", not a decorative effect on
 *    every element.
 * `strip` is an optional array of up to 5 { value, label } live KPIs
 * rendered along the base of the hero (the "system strip").
 */
export default function AgentCoreHero({ strip }) {
  const navigate = useNavigate();
  const pointerRef = usePointerParallax();
  const scrollRef = useScrollParallax();
  const perfTier = useScenePerformanceTier(); // full | reduced | static

  return (
    <section
      className="hero-3d"
      ref={(node) => {
        pointerRef.current = node;
        scrollRef.current = node;
      }}
    >
      <div className="hero-3d-main">
        <div className="hero-3d-copy" data-depth="fg" data-scroll-speed="0.18">
          <div className="hero-3d-eyebrow">TRIALMIND / AGENTIC OPERATIONS</div>
          <h1 className="hero-3d-title">
            Screen. Explain.<br />
            <span>Review.</span>
          </h1>
          <p className="hero-3d-sub">
            One AI system that reads trial protocols, matches eligible patients,
            retrieves the evidence behind every decision, and hands the final
            call to a human — continuously, auditably, across every study.
          </p>
          <div className="hero-3d-actions">
            <button className="hero-3d-primary" onClick={() => navigate("/trialmind")}>
              Start Screening
            </button>
            <button className="hero-3d-secondary" onClick={() => navigate("/audit")}>
              View Audit Trail
            </button>
          </div>
          <div className="hero-3d-micro">SYNTHETIC DATA · HUMAN-IN-THE-LOOP · AUDITABLE WORKFLOW</div>
        </div>
        <div className="hero-3d-scene" data-depth="mid" data-scroll-speed="0.1">
          <SceneErrorBoundary fallback={<SceneFallback />}>
            {perfTier === "static" ? (
              <SceneFallback />
            ) : (
              <Suspense fallback={<SceneFallback />}>
                <AgentCoreScene />
              </Suspense>
            )}
          </SceneErrorBoundary>
          <div className="hero-3d-scene-label" data-depth="fg">
            <strong>AGENT CORE</strong>
            <span>READY · 03 TOOLS · RAG ONLINE</span>
          </div>
        </div>
      </div>

      {strip && strip.length > 0 && (
        <div className="hero-strip" data-depth="bg" data-scroll-speed="0.04">
          {strip.slice(0, 5).map((item) => (
            <div className="hero-strip-item" key={item.label}>
              <div className="hero-strip-value">{item.value}</div>
              <div className="hero-strip-label">{item.label}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
