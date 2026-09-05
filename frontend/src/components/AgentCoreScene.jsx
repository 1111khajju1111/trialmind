import { Canvas, useFrame } from "@react-three/fiber";
import { Float, CatmullRomLine } from "@react-three/drei";
import { useRef, useMemo } from "react";

// -----------------------------------------------------------------------
// Maps a raw backend timeline step_name (see agent_orchestrator.py) to a
// scene phase + which node should be "active" right now. This is the one
// place agent state becomes visual state -- TrialMind.jsx just passes the
// last step_name + running/error flags in, it doesn't know about 3D.
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
      // The core itself is the active element here, not the patients
      // node -- the system isn't receiving new patient data anymore, it's
      // reasoning over what it already has. No NODE_DEFS node uses "core"
      // as its key, so none of the four workflow nodes lights up while
      // this is active; visual focus stays entirely on the core, whose
      // "evaluating" phase already renders amber and pulses faster.
      return { phase: "evaluating", activeNode: "core" };
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

// Igloo-inspired light-canvas pass: same four phases, same meaning
// (cyan = normal system activity, amber = actively evaluating, teal-green
// = settled/completed, red = error) -- only the hex values and pulse
// bases changed, deepened/more saturated so the glow still reads against
// a white canvas instead of the black background this was originally
// tuned for. `deriveSceneState` above (the actual state logic) is
// untouched.
const PHASE_COLOR = {
  idle: { emissive: "#0e93a6", base: 1.0 },
  active: { emissive: "#0e93a6", base: 1.3 },
  evaluating: { emissive: "#c98a1d", base: 1.6 },
  completed: { emissive: "#12876a", base: 1.4 },
  error: { emissive: "#d64555", base: 1.6 },
};

// -----------------------------------------------------------------------
// INTELLIGENCE CORE -- a layered engine, not a single spinning shape:
// an outer wireframe shell (the network boundary), an inner solid nucleus
// (the reasoning engine itself, counter-rotating), and a tilted halo ring
// (a "sensor" band) that reads as an instrument rather than decoration.
// -----------------------------------------------------------------------
function Core({ phase }) {
  const shellRef = useRef();
  const shellMatRef = useRef();
  const nucleusRef = useRef();
  const nucleusMatRef = useRef();
  const ringRef = useRef();

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (shellRef.current) {
      shellRef.current.rotation.y = t * 0.16;
      shellRef.current.rotation.x = Math.sin(t * 0.3) * 0.08;
    }
    if (nucleusRef.current) {
      // Counter-rotates against the shell -- two independent moving parts
      // read as "engine" rather than "one rotating ornament". Speeds up
      // during evaluation, since that's the moment the core itself is
      // doing the work rather than passing data through.
      const nucleusSpeed = phase === "evaluating" ? 0.95 : 0.34;
      nucleusRef.current.rotation.y = -t * nucleusSpeed;
      nucleusRef.current.rotation.z = t * (phase === "evaluating" ? 0.32 : 0.12);
    }
    if (ringRef.current) {
      const ringSpeed = phase === "error" ? 1.4 : phase === "evaluating" ? 0.8 : 0.22;
      ringRef.current.rotation.z = t * ringSpeed;
      ringRef.current.rotation.x = Math.PI / 2.3;
    }

    const pulseSpeed = phase === "evaluating" ? 6 : phase === "error" ? 9 : 1.6;
    const { base } = PHASE_COLOR[phase] || PHASE_COLOR.idle;
    // Deterministic, not random: two off-ratio sine waves summed together
    // produce an irregular-looking but fully reproducible wobble, which
    // reads as "the network is destabilized" rather than "the mesh is
    // jittering because of frame noise". Math.random() here would add a
    // new random value every frame, which looks like visual static rather
    // than intentional instability.
    const instability = phase === "error"
      ? Math.sin(t * 13.7) * 0.4 + Math.sin(t * 7.3) * 0.35
      : 0;
    const pulse = base + Math.sin(t * pulseSpeed) * (phase === "idle" ? 0.15 : 0.6) + instability;
    if (shellMatRef.current) shellMatRef.current.emissiveIntensity = Math.max(0.4, pulse);
    if (nucleusMatRef.current) nucleusMatRef.current.emissiveIntensity = Math.max(0.55, pulse * 1.1);
  });

  const color = (PHASE_COLOR[phase] || PHASE_COLOR.idle).emissive;

  return (
    <Float speed={1.1} rotationIntensity={0.15} floatIntensity={0.4}>
      <group>
        {/* Wireframe shell: a mid-tone base color (rather than the old
            near-white) so the edges read as structure even where the
            phase glow is faint, without an environment map to reflect.
            Enlarged so the core reads as the single "big ball" the
            structure wraps around, rather than a small ornament. */}
        <mesh ref={shellRef}>
          <icosahedronGeometry args={[1.55, 3]} />
          <meshStandardMaterial
            ref={shellMatRef}
            color="#3a4a63"
            emissive={color}
            emissiveIntensity={1.1}
            roughness={0.4}
            metalness={0.25}
            wireframe
          />
        </mesh>
        {/* Nucleus: dark charcoal base (not white/mirror) so it reads as
            a solid engine core lit by its own colored glow, reliably,
            without depending on scene reflections. A sphere (not an
            octahedron) so the "big ball" reads unambiguously as a ball. */}
        <mesh ref={nucleusRef}>
          <sphereGeometry args={[0.62, 32, 32]} />
          <meshStandardMaterial
            ref={nucleusMatRef}
            color="#1c2230"
            emissive={color}
            emissiveIntensity={1.4}
            roughness={0.35}
            metalness={0.35}
          />
        </mesh>
        <mesh ref={ringRef}>
          <torusGeometry args={[2.0, 0.014, 8, 96]} />
          <meshBasicMaterial color={color} transparent opacity={0.75} />
        </mesh>
      </group>
    </Float>
  );
}

// -----------------------------------------------------------------------
// DOUBLE-HELIX BACKBONE -- purely structural/decorative geometry (no
// state ties) that gives the network its DNA read: two counter-phased
// spiral strands wrapping a vertical axis, with periodic "rungs"
// connecting them like base pairs. `helixPoint` is a plain function, not
// tied to React or animation state, so the strand/rung geometry can be
// computed once with useMemo and never touches deriveSceneState.
// -----------------------------------------------------------------------
const HELIX_TOP = 2.0;
const HELIX_BOTTOM = -2.0;
const HELIX_RADIUS = 0.95;
const HELIX_TURNS = 1.65;

function helixPoint(t, strand) {
  const angle = t * HELIX_TURNS * Math.PI * 2 + (strand === 1 ? Math.PI : 0);
  const y = HELIX_TOP + t * (HELIX_BOTTOM - HELIX_TOP);
  return [Math.cos(angle) * HELIX_RADIUS, y, Math.sin(angle) * HELIX_RADIUS];
}

function HelixBackbone() {
  const strandA = useMemo(
    () => Array.from({ length: 48 }, (_, i) => helixPoint(i / 47, 0)),
    []
  );
  const strandB = useMemo(
    () => Array.from({ length: 48 }, (_, i) => helixPoint(i / 47, 1)),
    []
  );
  const rungs = useMemo(
    () => Array.from({ length: 13 }, (_, i) => {
      const t = i / 12;
      return [helixPoint(t, 0), helixPoint(t, 1)];
    }),
    []
  );

  return (
    <group>
      <CatmullRomLine points={strandA} color="#9aa4b8" lineWidth={1.4} transparent opacity={0.55} />
      <CatmullRomLine points={strandB} color="#9aa4b8" lineWidth={1.4} transparent opacity={0.55} />
      {rungs.map((pts, i) => (
        <CatmullRomLine key={i} points={pts} color="#c3c9d6" lineWidth={1} transparent opacity={0.4} />
      ))}
    </group>
  );
}

// Slow, continuous, self-contained rotation for the whole helix + core
// group -- anchored to the viewport (no pointer/scroll input), which is
// exactly the "subtle internal motion, spatially stable" the brief asks
// for: the structure moves, the frame it sits in does not.
function HelixSpin({ children }) {
  const ref = useRef();
  useFrame((state) => {
    if (ref.current) ref.current.rotation.y = state.clock.elapsedTime * 0.08;
  });
  return <group ref={ref}>{children}</group>;
}

function Scene({ phase }) {
  return (
    <>
      {/* Lighting retuned for a transparent canvas over a white/off-white
          page: no environment map, so geometry needs to be directly and
          evenly lit rather than relying on dark-background bloom. */}
      <ambientLight intensity={0.95} />
      <hemisphereLight args={["#ffffff", "#dfe4ee", 0.7]} />
      <pointLight position={[3, 3, 4]} intensity={10} color="#eaf6ff" />
      <pointLight position={[-3, -2, 2]} intensity={7} color="#eef0ff" />
      <pointLight position={[0, 5, -4]} intensity={5} color="#ffffff" />

      {/* Just two elements, per the simplified visual brief: the DNA
          double-helix structure, and one big ball (the Intelligence Core)
          at its center. No workflow node spheres, no comet-particle
          balls, no error-burst balls scattered around it. */}
      <HelixSpin>
        <HelixBackbone />
        <Core phase={phase} />
      </HelixSpin>

      {/* No CameraControls: the operational dashboard/console must stay
          completely spatially stable -- no orbit, no zoom, no camera
          manipulation of any kind. The Canvas's own fixed camera prop
          (position [0,0,5.6], default rotation) already looks straight at
          the origin, so removing CameraControls entirely (rather than
          disabling it) leaves that framing untouched with zero
          interactive controls left mounted. */}
    </>
  );
}

// Drop-in <canvas> wrapper so this can be embedded in any panel; the
// canvas itself has no background color, so it sits directly on whatever
// page background it's placed over (a light/off-white page, per the
// Igloo-inspired pass -- see DNADashboardHero.jsx and TrialMindConsole.jsx).
// Pass `lastStep` (the most recent timeline step_name), `running`, and
// `hasError` -- the scene derives its own phase/active-node from those,
// so callers never need to know the visual vocabulary.
export default function AgentCoreScene({ lastStep = null, running = false, hasError = false }) {
  const { phase } = useMemo(
    () => deriveSceneState({ lastStep, running, hasError }),
    [lastStep, running, hasError]
  );
  // Performance tier (P1 polish): full-power displays render at native
  // pixel ratio, everything else (low core count, small/mobile viewport,
  // or an explicit data-saver preference) is capped at 1x DPR and drops
  // shadows -- the geometry and motion are unchanged, only render cost.
  const isLowPower =
    typeof navigator !== "undefined" &&
    ((navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) ||
      (typeof window !== "undefined" && window.innerWidth < 720));
  return (
    <Canvas
      camera={{ position: [0, 0, 5.6], fov: 42 }}
      dpr={isLowPower ? 1 : [1, 2]}
      shadows={!isLowPower}
    >
      <Scene phase={phase} />
    </Canvas>
  );
}
