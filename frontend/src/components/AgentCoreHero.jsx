import { Suspense } from "react";
import { useNavigate } from "react-router-dom";
import AgentCoreScene from "./AgentCoreScene.jsx";
import SceneErrorBoundary from "./SceneErrorBoundary.jsx";

const SceneFallback = () => (
  <div className="hero-3d-scene-fallback">
    <div className="hero-3d-scene-fallback-orb" />
  </div>
);

export default function AgentCoreHero() {
  const navigate = useNavigate();

  return (
    <section className="hero-3d">
      <div className="hero-3d-copy">
        <div className="hero-3d-eyebrow">PHARMA AI / AGENTIC OPERATIONS</div>
        <h1 className="hero-3d-title">
          Pharma AI<br />
          <span>Command Center</span>
        </h1>
        <p className="hero-3d-sub">
          AI-powered clinical trial intelligence, patient matching, regulatory
          automation and laboratory operations — multiple agents continuously
          monitoring and automating pharmaceutical operations.
        </p>
        <div className="hero-3d-actions">
          <button className="hero-3d-primary" onClick={() => navigate("/trialmind")}>
            Start Screening
          </button>
        </div>
        <div className="hero-3d-micro">SYNTHETIC DATA · HUMAN-IN-THE-LOOP · AUDITABLE WORKFLOW</div>
      </div>
      <div className="hero-3d-scene">
        <SceneErrorBoundary fallback={<SceneFallback />}>
          <Suspense fallback={<SceneFallback />}>
            <AgentCoreScene />
          </Suspense>
        </SceneErrorBoundary>
        <div className="hero-3d-scene-label">
          <strong>AGENT CORE</strong>
          <span>READY · 03 TOOLS · RAG ONLINE</span>
        </div>
      </div>
    </section>
  );
}
