import { Canvas, useFrame } from "@react-three/fiber";
import { Float, CatmullRomLine, Text } from "@react-three/drei";
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
            phase glow is faint, without an environment map to reflect. */}
        <mesh ref={shellRef}>
          <icosahedronGeometry args={[1.15, 3]} />
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
            without depending on scene reflections. */}
        <mesh ref={nucleusRef}>
          <octahedronGeometry args={[0.46, 1]} />
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
          <torusGeometry args={[1.55, 0.012, 8, 96]} />
          <meshBasicMaterial color={color} transparent opacity={0.75} />
        </mesh>
      </group>
    </Float>
  );
}

// -----------------------------------------------------------------------
// DATA-FLOW PARTICLES -- small comets streaming along a node's connection.
// `direction: "in"` (protocol, patients) streams toward the core, so the
// scene reads as "the agent is taking in protocol/patient data". `"out"`
// (evidence, review) streams away from the core, reading as "evidence and
// the decision are what the core produces". Positions are updated purely
// via refs inside useFrame -- no React re-render per frame, so this stays
// cheap even with several connections animating at once.
// -----------------------------------------------------------------------
function FlowParticles({ from, to, active, color, count = 5, speed = 0.55 }) {
  const refs = useRef([]);
  const offsets = useMemo(() => Array.from({ length: count }, (_, i) => i / count), [count]);

  useFrame((state) => {
    const t0 = (state.clock.elapsedTime * speed) % 1;
    offsets.forEach((offset, i) => {
      const mesh = refs.current[i];
      if (!mesh) return;
      if (!active) {
        mesh.visible = false;
        return;
      }
      mesh.visible = true;
      const t = (t0 + offset) % 1;
      mesh.position.set(
        from[0] + (to[0] - from[0]) * t,
        from[1] + (to[1] - from[1]) * t,
        from[2] + (to[2] - from[2]) * t
      );
      // Comet-trail feel: fade in/out near each end of the run instead of
      // popping in at full size.
      const edgeFade = Math.min(t, 1 - t) * 4;
      const scale = Math.min(1, edgeFade) * 0.075;
      mesh.scale.setScalar(scale);
    });
  });

  return (
    <>
      {offsets.map((_, i) => (
        <mesh key={i} ref={(el) => (refs.current[i] = el)}>
          <sphereGeometry args={[1, 8, 8]} />
          <meshBasicMaterial color={color} transparent opacity={0.9} />
        </mesh>
      ))}
    </>
  );
}

// Error state: instead of a directed stream, a short burst of particles
// scatters outward from the core in irregular directions -- reads as the
// network being interrupted rather than continuing its normal flow.
function ErrorBurst({ active }) {
  const refs = useRef([]);
  const dirs = useMemo(
    () => Array.from({ length: 8 }, () => [
      (Math.random() - 0.5) * 2,
      (Math.random() - 0.5) * 2,
      (Math.random() - 0.5) * 2,
    ]),
    []
  );
  useFrame((state) => {
    if (!active) {
      refs.current.forEach((m) => m && (m.visible = false));
      return;
    }
    const t = (state.clock.elapsedTime * 0.9) % 1;
    dirs.forEach((dir, i) => {
      const mesh = refs.current[i];
      if (!mesh) return;
      mesh.visible = true;
      const dist = t * 2.1;
      mesh.position.set(dir[0] * dist, dir[1] * dist, dir[2] * dist);
      mesh.scale.setScalar(Math.max(0, 0.07 * (1 - t)));
    });
  });
  return (
    <>
      {dirs.map((_, i) => (
        <mesh key={i} ref={(el) => (refs.current[i] = el)}>
          <sphereGeometry args={[1, 6, 6]} />
          <meshBasicMaterial color="#ff5d5d" transparent opacity={0.85} />
        </mesh>
      ))}
    </>
  );
}

// One workflow node. `active` drives a brightness ramp (via useFrame, not
// a React re-render per frame) so state changes feel like a smooth pulse
// rather than a jump cut.
function Node({ position, label, color, activeColor, active, errored }) {
  const matRef = useRef();
  const targetRef = useRef(0.5);
  useFrame((state) => {
    targetRef.current = errored ? 1.5 : active ? 1.3 : 0.5;
    if (matRef.current) {
      matRef.current.emissiveIntensity +=
        (targetRef.current - matRef.current.emissiveIntensity) * 0.08;
      if (active) {
        matRef.current.emissiveIntensity += Math.sin(state.clock.elapsedTime * 5) * 0.15;
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
            emissive={errored ? "#d64555" : active ? activeColor : color}
            emissiveIntensity={0.6}
            metalness={0.3}
            roughness={0.4}
          />
        </mesh>
      </Float>
      {/* Dark/charcoal label text -- the previous near-white color was
          tuned for a black canvas and would be invisible on white. */}
      <Text
        position={[0, -0.55, 0]}
        fontSize={label.length > 10 ? 0.19 : 0.24}
        color={active ? "#12151c" : "#6b7488"}
        anchorX="center"
        anchorY="middle"
        maxWidth={1.6}
        textAlign="center"
        letterSpacing={0.02}
      >
        {label}
      </Text>
    </group>
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

// Protocol, Patients (inputs, feeding the core) and Evidence, Review
// (outputs, produced by the core), placed along the double-helix backbone
// -- alternating strands top to bottom -- so the arrangement reads as a
// DNA ladder (Protocol -> Patients -> Evidence -> Human Review) wrapped
// around the Intelligence Core at its center, rather than a flat cross of
// four dots. Deepened/more saturated colors than the original pastel set
// so each node stays legible against a white canvas.
const NODE_DEFS = [
  { key: "protocol", position: helixPoint(0.1, 0), label: "PROTOCOL", color: "#8b93a6", activeColor: "#0ea5b8", direction: "in" },
  { key: "patients", position: helixPoint(0.38, 1), label: "PATIENTS", color: "#8b93a6", activeColor: "#5b6fe0", direction: "in" },
  { key: "evidence", position: helixPoint(0.62, 0), label: "EVIDENCE", color: "#8b93a6", activeColor: "#c98a1d", direction: "out" },
  { key: "review", position: helixPoint(0.9, 1), label: "HUMAN REVIEW", color: "#8b93a6", activeColor: "#d9622f", direction: "out" },
];
const ORIGIN = [0, 0, 0];

function Scene({ phase, activeNode }) {
  const errored = phase === "error";
  const allSettled = phase === "completed";

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

      <HelixSpin>
        <HelixBackbone />
        <Core phase={phase} />

        {NODE_DEFS.map((node) => {
          const isActive = allSettled || activeNode === node.key;
          return (
            <Node
              key={node.key}
              position={node.position}
              label={node.label}
              color={node.color}
              activeColor={node.activeColor}
              active={isActive}
              errored={errored}
            />
          );
        })}

        {NODE_DEFS.map((node) => (
          <CatmullRomLine
            key={`line-${node.key}`}
            points={[[0, 0, 0], node.position.map((v) => v * 0.5), node.position]}
            color={errored ? "#d64555" : allSettled || activeNode === node.key ? node.activeColor : "#c3c9d6"}
            lineWidth={allSettled || activeNode === node.key ? 2 : 1}
          />
        ))}

        {/* Directional data flow: input nodes stream toward the core while
            they're active; output nodes stream away from the core once the
            run has moved past evaluation, i.e. evidence/decision are what
            the core is now producing. During "completed", every connection
            carries a slow, faint flow -- the network settling into a state
            where the whole path is visibly a live system, not four inert
            dots around a shape. */}
        {!errored && NODE_DEFS.map((node) => {
          const isActive = allSettled || activeNode === node.key;
          const [from, to] = node.direction === "in" ? [node.position, ORIGIN] : [ORIGIN, node.position];
          return (
            <FlowParticles
              key={`flow-${node.key}`}
              from={from}
              to={to}
              active={isActive}
              color={node.activeColor}
              speed={allSettled ? 0.22 : 0.6}
              count={allSettled ? 3 : 5}
            />
          );
        })}

        <ErrorBurst active={errored} />
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
  const { phase, activeNode } = useMemo(
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
      <Scene phase={phase} activeNode={activeNode} />
    </Canvas>
  );
}
