import { Canvas, useFrame } from "@react-three/fiber";
import { CameraControls, Float, CatmullRomLine, Text } from "@react-three/drei";
import { useRef, useMemo } from "react";

// -----------------------------------------------------------------------
// Maps a raw backend timeline step_name (see agent_orchestrator.py) to a
// scene phase + which orbit node should be "active" right now. This is the
// one place agent state becomes visual state -- TrialMind.jsx just passes
// the last step_name + running/error flags in, it doesn't know about 3D.
// -----------------------------------------------------------------------
export function deriveSceneState({ lastStep, running, hasError }) {
  if (hasError) return { phase: "error", activeNode: null };
  if (!running && lastStep === "run_completed") return { phase: "completed", activeNode: null };
  if (!running && !lastStep) return { phase: "idle", activeNode: null };

  switch (lastStep) {
    case "run_started":
    case "protocol_loaded":
      return { phase: "active", activeNode: "protocol" };
    case "search_patients":
      return { phase: "active", activeNode: "patients" };
    case "evaluate_eligibility":
      return { phase: "evaluating", activeNode: "patients" };
    case "evidence_retrieved":
    case "evidence_not_found":
      return { phase: "active", activeNode: "evidence" };
    case "ranking_completed":
      return { phase: "active", activeNode: "review" };
    case "run_timeout":
    case "agent_error":
    case "tool_error":
      return { phase: "error", activeNode: null };
    default:
      return running ? { phase: "active", activeNode: "protocol" } : { phase: "idle", activeNode: null };
  }
}

const PHASE_COLOR = {
  idle: { emissive: "#36d9c3", base: 1.4 },
  active: { emissive: "#36d9c3", base: 2.0 },
  evaluating: { emissive: "#ffd166", base: 2.6 },
  completed: { emissive: "#54e7d0", base: 2.2 },
  error: { emissive: "#ff5d5d", base: 2.4 },
};

// Central glowing icosahedron representing the agent / AI engine itself.
// Rotation is always-on (ambient life); pulse speed and color communicate
// what the agent is actually doing right now.
function Core({ phase }) {
  const ref = useRef();
  const matRef = useRef();
  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y = state.clock.elapsedTime * 0.18;
    ref.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.35) * 0.08;

    const pulseSpeed = phase === "evaluating" ? 6 : phase === "error" ? 4 : 1.6;
    const { base } = PHASE_COLOR[phase] || PHASE_COLOR.idle;
    const pulse = base + Math.sin(state.clock.elapsedTime * pulseSpeed) * (phase === "idle" ? 0.15 : 0.6);
    if (matRef.current) matRef.current.emissiveIntensity = Math.max(0.6, pulse);
  });
  const color = (PHASE_COLOR[phase] || PHASE_COLOR.idle).emissive;
  return (
    <Float speed={1.2} rotationIntensity={0.2} floatIntensity={0.5}>
      <mesh ref={ref}>
        <icosahedronGeometry args={[1.15, 3]} />
        <meshStandardMaterial
          ref={matRef}
          color="#8fffea"
          emissive={color}
          emissiveIntensity={1.8}
          roughness={0.2}
          metalness={0.7}
          wireframe
        />
      </mesh>
    </Float>
  );
}

// One orbit node. `active` drives a brightness ramp (via useFrame, not a
// React re-render per frame) so state changes feel like a smooth pulse
// rather than a jump cut.
function Node({ position, label, color, activeColor, active, errored }) {
  const matRef = useRef();
  const targetRef = useRef(1.2);
  useFrame((state) => {
    targetRef.current = errored ? 3.0 : active ? 2.6 : 1.2;
    if (matRef.current) {
      matRef.current.emissiveIntensity +=
        (targetRef.current - matRef.current.emissiveIntensity) * 0.08;
      if (active) {
        matRef.current.emissiveIntensity += Math.sin(state.clock.elapsedTime * 5) * 0.25;
      }
    }
  });
  return (
    <group position={position}>
      <Float speed={1.3} floatIntensity={0.4}>
        <mesh>
          <sphereGeometry args={[active ? 0.34 : 0.26, 24, 24]} />
          <meshStandardMaterial
            ref={matRef}
            color={active ? activeColor : color}
            emissive={errored ? "#ff5d5d" : active ? activeColor : color}
            emissiveIntensity={1.2}
            metalness={0.8}
            roughness={0.18}
          />
        </mesh>
      </Float>
      <Text
        position={[0, -0.55, 0]}
        fontSize={0.24}
        color={active ? "#f4f7fb" : "#7f8a9d"}
        anchorX="center"
        anchorY="middle"
      >
        {label}
      </Text>
    </group>
  );
}

// Protocol, Patients, Evidence, Review -- the four workflow stages that
// orbit the core (Audit is represented by the dedicated audit trail UI
// outside the 3D scene, rather than a fifth redundant node in here).
const NODE_DEFS = [
  { key: "protocol", position: [2.4, 0.7, 0], label: "PROTOCOL", color: "#5c6b85", activeColor: "#b6fff5" },
  { key: "patients", position: [-2.2, 0.9, 0], label: "PATIENTS", color: "#5c6b85", activeColor: "#93a7ff" },
  { key: "evidence", position: [0, -1.9, 0], label: "EVIDENCE", color: "#5c6b85", activeColor: "#ffd166" },
  { key: "review", position: [2.0, -1.3, 0.6], label: "REVIEW", color: "#5c6b85", activeColor: "#ff9f6e" },
];

function Scene({ phase, activeNode }) {
  const errored = phase === "error";
  const allSettled = phase === "completed";

  return (
    <>
      <ambientLight intensity={0.7} />
      <pointLight position={[3, 3, 4]} intensity={20} color="#a8fff1" />
      <pointLight position={[-3, -2, 2]} intensity={12} color="#6f8cff" />
      {/* Fill lights stand in for an HDRI environment map so the scene
          never depends on an external network fetch (which would crash
          the whole Canvas if blocked, e.g. in locked-down deployments). */}
      <pointLight position={[0, 5, -4]} intensity={8} color="#ffffff" />
      <pointLight position={[4, -4, -2]} intensity={6} color="#8fffea" />
      <hemisphereLight args={["#8fb3ff", "#0a0f1e", 0.6]} />

      <Core phase={phase} />

      {NODE_DEFS.map((node) => (
        <Node
          key={node.key}
          position={node.position}
          label={node.label}
          color={node.color}
          activeColor={node.activeColor}
          active={allSettled || activeNode === node.key}
          errored={errored}
        />
      ))}

      {NODE_DEFS.map((node) => (
        <CatmullRomLine
          key={`line-${node.key}`}
          points={[[0, 0, 0], node.position.map((v) => v * 0.5), node.position]}
          color={errored ? "#ff5d5d" : allSettled || activeNode === node.key ? "#7fffea" : "#2b3547"}
          lineWidth={allSettled || activeNode === node.key ? 2 : 1}
        />
      ))}

      <CameraControls makeDefault minDistance={4} maxDistance={9} />
    </>
  );
}

// Drop-in <canvas> wrapper so this can be embedded in any panel without
// pulling the rest of the page into the 3D scene's dark visual language.
// Pass `lastStep` (the most recent timeline step_name), `running`, and
// `hasError` -- the scene derives its own phase/active-node from those,
// so callers never need to know the visual vocabulary.
export default function AgentCoreScene({ lastStep = null, running = false, hasError = false }) {
  const { phase, activeNode } = useMemo(
    () => deriveSceneState({ lastStep, running, hasError }),
    [lastStep, running, hasError]
  );
  return (
    <Canvas camera={{ position: [0, 0, 6], fov: 42 }}>
      <Scene phase={phase} activeNode={activeNode} />
    </Canvas>
  );
}
