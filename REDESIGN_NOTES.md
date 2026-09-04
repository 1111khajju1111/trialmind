# TrialMind UI/UX Redesign — Implementation Notes

Applied against `pharma_platform_v6.zip` per `TrialMind_Award_Winning_UI_UX_Plan.pdf`.

## What's implemented (P0 pass)

**Brand shell (P0.1)**
- New design-token system in `frontend/src/index.css`: near-black graphite base,
  a fixed semantic accent system (cyan = system/AI, violet = intelligence/evidence,
  green = approved, amber = needs review, red = blocking risk), tabular numerals,
  a display type scale, and brutalist utility classes (`.tm-decisive`, hard 2px
  frames on decision moments).
- Platform chrome renamed from "PharmaAI" to **TrialMind**, with a new geometric
  mark (`IconMark` in `design-system/icons.jsx`) standing in for the Agent Core.
- New single-icon-family system (`frontend/src/design-system/icons.jsx`) — one
  1.75px-stroke, 24×24 line-icon set. Emoji removed from primary navigation,
  the dashboard, the TrialMind flagship page, and candidate-review state icons.

**Command hero (P0.2)** — `AgentCoreHero.jsx`
- Full-viewport hero retained/upgraded with the 3D Agent Core, kinetic display
  type, and a new **system strip**: 3–5 live KPIs (active studies, candidates
  screened, evidence-backed matches, pending review, audit events) rendered
  along the base of the hero, fed from real dashboard data.
- Added a secondary CTA ("View Audit Trail") so the hero offers one dominant
  action plus one clear secondary, per the brief.

**Run experience / candidate review (P0.3 / P0.4)**
- The existing state-machine run experience (Agent Core scene → pipeline strip
  → cinematic timeline → evidence trace → human review gate) already matched
  the brief's structure well, so this pass focused on visual language: brutalist
  `APPROVE`/`REJECT` buttons (hard 2px borders, high-contrast fills, no pill
  softness) replacing the previous default buttons, and icon-based pass/fail/
  warning marks in the evidence trace instead of emoji glyphs.

**Navigation**
- Top nav rebuilt as a quieter control surface (smaller radius, tighter type,
  icon system) rather than a pill-heavy row competing with page content.
- Mobile bottom nav and theme toggle updated to the same icon family.

**Dashboard (P0)**
- Recomposed around the command hero + system strip, KPI groups per domain
  (portfolio, pharmacovigilance, recruitment), and the AI agent roster —
  same information, restyled with the new token system and icon set, one
  primary read-order top to bottom.

## What's inherited automatically
Every other page (Studies, Study Detail, Patients, Safety, Compliance,
Regulatory Drafting, Lab Scheduling, Audit Trail, Interoperability) uses the
same `.card`, `.badge`, `.gbtn`, `.kpi-*`, `.agent-*`, form and alert classes
that were restyled in `index.css`, so they pick up the new color system,
typography, spacing and card treatment without any per-page edits.

## Not yet done (flagged, not silently skipped)
- Those secondary pages still have their original emoji icons in local JSX
  (e.g. `StudyDetail.jsx` has the most, ~24 glyphs) rather than the new icon
  family — visually they already read as part of the same system because of
  the token/color pass, but a full "remove every emoji" sweep per page is the
  next increment.
- Scroll parallax, hover-depth on cards, and evidence-reveal choreography
  (P1/P2 motion spec) aren't wired up yet — current motion is limited to the
  existing hover-lift, pulse, and 3D scene behavior.
- No build tool was available in this environment to run `npm install` /
  `vite build` against the real dependency set, so changes were reviewed by
  hand (brace/paren balance, JSX structure, cross-file class usage) rather
  than compiled. Worth a `npm install && npm run dev` smoke test before deploy.

## Update — real scroll/parallax system added

Addressed the follow-up review's core critique: there was motion (3D, pulses,
hover-lift) but no deliberate scroll-choreographed parallax. Added:

- `frontend/src/design-system/motion.js` — two scoped hooks:
  - `usePointerParallax()`: elements tagged `data-depth="fg|mid|bg"` shift on
    pointer move at ~8px / 4px / 1.5px respectively (matches the brief's
    6–10 / 3–5 / 1–2px amplitude spec), driven by `requestAnimationFrame`
    writing `transform` directly — no React re-render per mouse move.
  - `useScrollParallax()`: elements tagged `data-scroll-speed="0.04–0.22"`
    drift at different rates as the section crosses the viewport, gated by
    an `IntersectionObserver` so the scroll listener only does work while
    the section is actually on screen.
  - Both fully no-op under `prefers-reduced-motion: reduce`.
- Wired into `AgentCoreHero.jsx`: the headline/CTA layer is foreground
  (fastest on both pointer and scroll), the Agent Core 3D frame is
  midground, and the KPI system strip is background (slowest) — genuine
  layered depth on the one focal moment, not applied to tables or dense
  clinical content per the brief's "avoid" list.
- `design-system/Reveal.jsx` + `.tm-reveal` CSS: IntersectionObserver-based
  progressive reveal, applied to the dashboard's portfolio/recruitment/agent
  sections and to the TrialMind candidate-review groups (potential → needs
  review → excluded reveal in sequence with staggered delay), so results
  choreograph in as you scroll rather than all appearing at once.

## On the "vite isn't installed" build report

Checked this myself: `package.json` and `package-lock.json` dependencies
match exactly (react, react-router-dom, three, @react-three/fiber,
@react-three/drei, axios, vite, @vitejs/plugin-react — no stray packages).
`npm install` failed in *this* sandbox with a 403 while resolving a
transitive dependency of `@react-three/drei` (`zustand`), because this
environment's network access is disabled entirely, not because of anything
in the repo. Locally or in CI with normal registry access, `cd frontend &&
npm install && npm run build` should work as-is. If it doesn't, that's worth
a fresh look, but nothing in this pass changed dependencies.

## Update — emoji sweep on secondary pages

Closed out the item flagged in the first pass as "not yet done": every
remaining literal emoji glyph in `StudyDetail.jsx`, `Regulatory.jsx`,
`Safety.jsx`, `LabScheduling.jsx`, `Interoperability.jsx`, `AuditTrail.jsx`,
`RegulatoryDrafting.jsx`, and `Studies.jsx` (66 occurrences across 8 files)
is now the single 24×24, 1.75px-stroke icon family instead.

- Added 9 new icons to `design-system/icons.jsx` to cover glyphs the
  original set didn't have: `IconBuilding` (sites/facilities), `IconCalendar`
  (milestones/dates), `IconClipboard` (cases/logs), `IconAlertCircle`
  (SAE/critical alerts — a filled-circle mark distinct from `IconWarning`'s
  triangle, so severity level stays visually distinguishable), `IconFlask`
  (equipment), `IconMicroscope` (samples), `IconExport` (data export),
  `IconMinus` (neutral/not-registered state), `IconCompass` (agent runs),
  and `IconDot` (a filled circle that takes a `color` prop — replaces the
  🟢🟡🔴 status-dot pattern using the existing `--accent-emerald` /
  `--accent-amber` / `--accent-red` tokens instead of emoji color).
- `TrialMind.jsx`, `Dashboard.jsx`, `CandidateCard.jsx`, and
  `RegulatoryDrafting.jsx`'s `✓`/`→`/`↓` characters were left as-is —
  those are plain typographic glyphs (arrows, checkmark), not colorful
  emoji, and are already used consistently as pipeline/flow punctuation
  elsewhere in the same files.
- Followed the existing convention (see `Dashboard.jsx`,
  `CandidateCard.jsx`) of importing icons by name from
  `design-system/icons.jsx` rather than the `<Icon name="..."/>` wrapper,
  so `grep`-ability and per-file import lists stay consistent with the rest
  of the codebase.
- Verified by hand (no build tool in this sandbox, same constraint as the
  previous pass): zero emoji remain outside the two typographic checkmarks
  noted above; every icon import in the eight edited files resolves to a
  real export in `icons.jsx`, is actually used in JSX, and every icon used
  in JSX has a corresponding import; bracket/brace/paren counts balance in
  all nine touched files. Still worth a real `npm run build` before deploy.

## Update — TrialMind flagship page redesign + signature run animation

Addressed the review's single biggest flagged gap: the homepage hero and
`/trialmind` read as two different products. `/trialmind` previously opened
with a conventional "TRIALMIND / Autonomous Recruitment Engine" header and
a separate boxed `agent-core-frame`, visually unrelated to the cinematic
homepage hero built in an earlier pass.

- **New `components/TrialMindConsole.jsx`** replaces that old header. It's
  built on the *exact same* `hero-3d` CSS classes as the homepage's
  `AgentCoreHero` (same pointer/scroll parallax hooks, same eyebrow/title/
  scene/strip layout) so the two screens are now demonstrably the same
  design system, not just a similar palette. Content is run-specific
  instead of generic: eyebrow reads "TRIALMIND / RECRUITMENT", the live
  pipeline (PROTOCOL → PATIENTS → EVIDENCE → HUMAN REVIEW) and an
  AGENT ACTIVE/IDLE/ERROR status line sit in the copy column, the Agent
  Core 3D scene keeps its live state-driven behavior, and the system strip
  now shows the *current* study, patient directory size, matched-candidate
  count, and the trial's machine-checkable-criteria percentage instead of
  portfolio-wide KPIs. The primary "Run Matching Agent" CTA and secondary
  "Add Trial Protocol" toggle moved into this hero as the one dominant
  action, per the brief's information-hierarchy rule — the old duplicate
  buttons lower on the page were removed.
- **Signature run animation.** Real backend timing is polled (not a fixed
  client-side clock), so rather than fake a scripted 2-second sequence,
  the choreography is wired to genuine state transitions:
  - The instant "Run Matching Agent" fires, the Agent Core scene frame
    gets a `.is-waking` class for ~900ms — a bright ring pulses outward
    (`@keyframes wakeRing`) as an immediate "the system just woke up"
    beat, before the first real timeline step lands from the backend.
  - The existing `pipeline-step is-active`/`is-passed` transitions (now
    reused inside the console) continue to light up PROTOCOL → PATIENTS →
    EVIDENCE → HUMAN REVIEW as each real step arrives from polling.
  - **New `components/RunCompleteSummary.jsx`** is the sequence's payoff:
    once `run_completed` lands, a connected three-stat panel appears
    *before* the candidate-list groups — Patients Screened → Potential
    Matches → Need Human Review, each an `AnimatedCounter` count-up,
    styled as one continuous story (arrows between stats) rather than
    three separate section headings arriving with no relationship to each
    other. It's wrapped in the existing `Reveal` component so it
    scroll-choreographs in like the groups below it.
  - All of the above respects `prefers-reduced-motion` (the wake-ring
    keyframe is disabled, `AnimatedCounter` jumps straight to the final
    value, `Reveal` shows its end state immediately) — same reduced-motion
    contract as the rest of the app, not a new exception.
- Removed the now-dead `.trialmind-hero*`, `.agent-core-frame`, and
  `.agent-core-pipeline` CSS rules (grep-verified zero remaining JSX
  references) since nothing renders them anymore. `.pipeline-step` /
  `.pipeline-arrow` were kept — they're reused inside the new console.
- Not done in this pass, still open from the review: the Agent Core 3D
  object itself (icosahedron + 4 orbit nodes) wasn't redesigned into the
  "clinical intelligence network" concept (data particles flowing core →
  evidence/review) — this pass focused on page-level composition and the
  run choreography, not the 3D asset itself. `CandidateCard` also wasn't
  touched yet (still the previous pass's brutalist-button version, not the
  reviewer's proposed 94%-eligibility-panel layout). Both remain queued.
- Verified by hand again: bracket/brace/paren balance across
  `TrialMind.jsx`, `TrialMindConsole.jsx`, `RunCompleteSummary.jsx`, and
  `index.css`; every new component import resolves to a real file; no
  leftover references to the removed CSS classes anywhere in `src/`.
  Still no `npm run build` in this sandbox (no network) — worth running
  for real before deploy, same caveat as every prior pass.

## Update — fixed two review-flagged bugs in the flagship console

1. **Pipeline chips were reading `running` instead of the confirmed
   timeline.** The previous logic marked PROTOCOL `is-passed` whenever
   `running === true`, regardless of whether `protocol_loaded` had
   actually arrived — same issue for PATIENTS defaulting to passed. Fixed
   with an explicit stage model in `TrialMindConsole.jsx`:
   `STAGE_PASSED_THROUGH` maps each confirmed `step_name` to how far the
   run has *actually* gotten (nothing is ever marked passed without a real
   backend event behind it), and `STAGE_ACTIVE`/a one-ahead fallback
   derives which stage is currently in flight, only while `running` is
   true. Simulated against the reviewer's full IDLE → RUNNING → PATIENT
   SEARCH → EVIDENCE → RANKING → COMPLETE table and it now matches
   state-for-state.
   - Also handled a case the review didn't test but the same bug class
     covers: if a run ends on `agent_error` / `tool_error` / `run_timeout`,
     the chips now fall back to the last real work step in the timeline
     (`pipelineStep` in `TrialMind.jsx`) so confirmed progress still shows
     as passed instead of every chip resetting to pending. `persistence_failed`
     already had a correct explicit mapping (ranking done, review not
     marked passed since the save itself failed).
   - Added `.pipeline-step.is-error` styling for this state.
2. **"Patients Screened" was using `matches.length`** (persisted
   `PatientMatch` records — a subset) instead of the actual search
   population. Fixed by parsing the real count out of the
   `search_patients` timeline step's `detail` text (backend emits
   `"Found {n} patient(s) with condition '...'"`) via
   `/Found (\d+) patient/`, falling back to `matches.length` only if that
   step is missing for some reason. `RunCompleteSummary` now receives this
   as `screened` instead of `matches.length`.
- Verified by hand: re-simulated the full pipeline state table in Python
  against the exact transition map now in the component (see above);
  bracket/brace/paren balance re-checked on both edited files.

## Update — Agent Core 3D redesign: clinical intelligence network

Replaced the generic "icosahedron + 4 orbiting nodes" scene with a version
built around the review's "input → intelligence → evidence → decision"
framing, entirely inside `components/AgentCoreScene.jsx`. No new npm
dependencies — everything here is built from primitives already available
in `three`/`@react-three/fiber`/`@react-three/drei` (icosahedron,
octahedron, torus geometries; `Float`, `CatmullRomLine`, `Text`), since
`npm install` still can't run in this sandbox.

- **Layered core, not one shape.** The core is now three independently
  moving parts instead of a single rotating wireframe: an outer wireframe
  icosahedron shell (the network boundary, same geometry as before), a
  solid octahedron nucleus nested inside it that counter-rotates against
  the shell, and a tilted thin torus "sensor ring" that spins around both.
  Two visibly independent moving parts read as an engine rather than a
  single decorative ornament.
- **Directional data-flow particles**, the review's main ask. Each of the
  four workflow nodes now has a `direction`: PROTOCOL and PATIENTS are
  `"in"` (small comet particles stream from the node toward the core while
  that stage is active — "the agent is taking in protocol/patient data"),
  EVIDENCE and DECISION (renamed from REVIEW for clarity) are `"out"`
  (particles stream from the core outward — "evidence and the decision are
  what the core produces"). Particle positions are driven entirely by refs
  inside `useFrame`, not React state, so this doesn't add per-frame
  re-renders on top of the existing node-pulse animation.
- **Repositioned nodes** top/left/right/bottom (protocol top, patients
  left, evidence right, decision bottom) instead of the previous scattered
  arrangement, so the layout itself reads as in → core → out rather than
  four symmetric dots with no directional story.
- **Completed state** now shows a slow, faint particle flow on *all four*
  connections simultaneously (not just brighter lines) — meant to read as
  "the network has settled into a stable, still-alive state" rather than
  simply stopping.
- **Error state** replaces the directed streams with a short outward
  particle burst from the core in irregular directions (`ErrorBurst`),
  plus a faster, jittery pulse on the core's emissive intensity — meant to
  read as the network being interrupted rather than continuing its normal
  flow, per the review's "breaking/interrupting the network" note.
- `deriveSceneState()` (backend step_name → phase/activeNode) and the
  `AgentCoreScene` component's public prop signature (`lastStep`,
  `running`, `hasError`) are both unchanged, so `TrialMindConsole.jsx` and
  `AgentCoreHero.jsx` — the two existing consumers — needed no changes.
- Not addressed: performance tiers (P2 in the review — full 3D → reduced →
  static fallback for low-power/mobile). The particle systems here are
  small (≤5 particles per connection, ≤8 for the error burst) and driven
  by lightweight ref updates, so this should be cheap, but it hasn't been
  measured on an actual low-power device since there's no way to profile
  in this sandbox.
- Verified by hand: bracket/brace/paren balance on the rewritten file;
  confirmed both existing consumers (`TrialMindConsole.jsx`,
  `AgentCoreHero.jsx`) still import the same default export with the same
  prop names, so nothing downstream needed touching; confirmed the three
  new geometry types used (`octahedronGeometry`, `torusGeometry`) are
  standard Three.js primitives, not additional dependencies. Still no real
  `npm run build`/visual render check possible here — this is a case where
  seeing it actually spin up matters more than usual, so it's worth
  spot-checking in a real browser before a demo.

## Update — Agent Core polish + CandidateCard V2 (flagship decision panel)

Two review-flagged Agent Core fixes, then the CandidateCard redesign that
was the last queued P0.

**Agent Core polish (`AgentCoreScene.jsx`):**
- `evaluate_eligibility` now maps to `activeNode: "core"` instead of
  `"patients"`. No `NODE_DEFS` entry has the key `"core"`, so none of the
  four workflow nodes lights up during evaluation — visual focus lands
  entirely on the core itself, which already renders amber and pulses
  faster during the `"evaluating"` phase. Also sped up the nucleus/ring
  rotation specifically during `"evaluating"` so the core visibly "does
  more work" at that moment rather than just changing color.
- Replaced the per-frame `Math.random()` jitter on the core's error-state
  pulse with a deterministic sum of two off-ratio sine waves
  (`sin(t*13.7)*0.4 + sin(t*7.3)*0.35`). Reads as intentional instability
  instead of frame noise, and is fully reproducible. Left the one
  `Math.random()` call inside `ErrorBurst`'s `useMemo` alone — that's
  computed once per mount for the burst's scatter directions, not
  per-frame, which is the correct place for randomness.

**CandidateCard V2 (`CandidateCard.jsx` + new CSS in `index.css`):**
Business logic, state, and handlers are byte-for-byte unchanged —
`onApprove`, `onReject`, `onGenerateOutreach`, `onSendOutreach`, the
outreach draft/finalize/send flow, `reviewerNote`, `splitDetail()`, the
`VERDICT_LABEL`/`STATUS_ICON` maps are all identical to before. Only the
visual composition and JSX structure changed, per the review's explicit
instruction to preserve logic and change hierarchy only.
- **New eligibility panel is the visual anchor**, placed right after the
  header: a large percentage, a thin progress bar (emerald ≥80%, amber
  50–79%, red below that), and an "X / Y criteria passed" caption. This
  reads immediately, before anyone has to parse individual criteria.
- **No fabricated confidence score.** The percentage is
  `Math.round(verifiedCount / totalCount * 100)` — derived from the same
  `criteria_results` the rest of the card already used — and is labeled
  "Criteria Passed" throughout, never "eligibility confidence" or
  similar, so it can't be misread as an AI certainty score the backend
  doesn't actually compute. If `totalCount` is 0 the panel shows "—"
  instead of a misleading 0%.
- **Compact checklist rows.** Each criterion's PASS/FAIL/REVIEW pill moved
  from a full-width bar at the bottom of its block to inline next to the
  criterion label, so the checklist reads top-to-bottom as a scannable
  list (label + pill) with patient-value/protocol-requirement/source
  detail still expanded beneath each one — nothing was hidden behind a
  click, only reflowed.
- **Section labels** ("Eligibility Checks", "Why This Decision?") make the
  reading order explicit: identity → score → checklist → rationale/
  evidence → human decision — matching the review's specified flow.
- Human review gate (`human-review-gate` / `tm-decisive` buttons) is
  unchanged in behavior, given slightly more top margin so it reads as a
  distinct final gate rather than blending into the evidence section
  above it. Still the only brutalist element in the card, per the
  minimalism-for-evidence / brutalism-for-decision split.
- Outreach draft workflow (generate → edit → finalize → advanced send) is
  completely untouched, still below the decision gate at the same visual
  weight as before.
- Removed the now-unused `STATUS_COLOR` constant (its only use, an inline
  style on the old bottom-of-block decision bar, was replaced by the
  `evidence-trace-pill.pass/fail/missing` CSS classes, which reuse the
  exact same color tokens as the app's existing `.badge.*` classes).
- Verified by hand: bracket/brace/paren balance on both edited files;
  confirmed every handler prop (`onApprove`, `onReject`,
  `onGenerateOutreach`, `onSendOutreach`) and the component's default
  export signature are unchanged so nothing calling `<CandidateCard />`
  needed touching. No visual render check possible in this sandbox (same
  caveat as always) — worth a real browser check before a demo,
  especially the progress-bar color thresholds and pill alignment on
  narrow/mobile widths.
