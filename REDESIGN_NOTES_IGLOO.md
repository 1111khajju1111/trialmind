# TrialMind — Igloo-Inspired UI/UX Pass (P0)

Applied against this codebase per `TrialMind_Igloo_Inspired_UI_UX_Change_Plan.pdf`.
This pass covers the plan's five P0 / CRITICAL REQUIREMENTS items only. P1
(TrialMind console restyle, candidate/evidence visual integration,
responsive QA) and P2 (performance polish, final accessibility) are not yet
started — flagged as the next increment rather than silently skipped.

## What's implemented (P0 pass)

**Light theme as the only demo theme**
- `context/ThemeContext.jsx`: no longer reads `localStorage` or
  `prefers-color-scheme`; the provider sets `data-theme="light"` once and
  exposes it as a constant. Dark mode's CSS tokens and `ThemeToggle.jsx`
  are left in the codebase for a future pass, but the toggle button is no
  longer rendered in `TopNavigation.jsx`, so there's no path back to dark
  in the demo build.
- `index.css`: the base `:root` token block (previously "fallback = dark")
  now matches the light palette directly, so there's no flash of dark
  before React hydrates. `html { color-scheme: light dark }` →
  `light`. The semantic accent colors (`--sys-cyan`, `--sys-violet`, etc.)
  now match the plan's palette (clinical blue `#2B6EF3`, cyan `#13A8C7`,
  etc.) in both the base tokens and the `[data-theme="light"]` override.

**Visible demo environment**
- `components/layout/DemoBanner.jsx` + its CSS: rebuilt as a light,
  high-contrast, text-first status strip — an outlined pill
  (`DEMO ENVIRONMENT`) plus `SYNTHETIC DATA` and
  `NOT FOR CLINICAL DECISION-MAKING`, all as real text (not color-only),
  with an accessible `role="status"` label. Same component, same mount
  point in `App.jsx`, so it stays visible on every page.

**DNA dashboard hero (replaces dashboard parallax)**
- New `components/DNADashboardHero.jsx`, used only on `pages/Dashboard.jsx`
  in place of `AgentCoreHero`. It does **not** call `usePointerParallax` or
  `useScrollParallax` — nothing in it reacts to pointer position or scroll
  offset. Per the plan's explicit note ("3D language ... already exists →
  reuse it"), it reuses `AgentCoreScene` unmodified: the same
  protocol / patients / evidence / human-review nodes around a core,
  which already match the plan's semantic mapping table. The 3D network
  keeps its own continuous motion (slow rotation, pulses, particle flow)
  but sits in a fixed, anchored frame — a contained dark "window" against
  the otherwise light, editorial page — plus a static text legend
  describing the four regions (Input / Input / Reasoning / Decision) for
  anyone who can't or doesn't want to rely on the 3D scene.
- `AgentCoreHero.jsx` and the pointer/scroll parallax hooks in
  `design-system/motion.js` are untouched and unused on the dashboard now,
  but left in place — `TrialMindConsole.jsx` still uses the same parallax
  system, and removing it there is explicitly a P1 item ("TrialMind
  console restyle"), not P0.

**Dashboard composition (density + narrative order)**
`pages/Dashboard.jsx` was reordered and thinned per the plan's suggested
read order:
1. DNA hero (dominant, includes the live 5-KPI system strip)
2. Lab alert banner (kept near the top — safety-relevant, not hidden)
3. "Active demo scenario" callout — active study count + pending-review
   count, one link into the live `/trialmind` workflow
4. Agent activity — a compact list (`.agent-activity-list`/-row) instead
   of five equal-weight cards
5. Operational modules (portfolio + pharmacovigilance + recruitment KPI
   grids) — collapsed by default behind a single toggle
   (`.operational-modules-toggle`), matching "collapsed/secondary" in the
   plan's table
6. Recent activity / audit trail preview, unchanged

## Not yet done (P1 / P2, flagged not skipped)
- `TrialMindConsole.jsx` (the `/trialmind` page) still uses
  `usePointerParallax` / `useScrollParallax` and the dark-hardcoded
  `.hero-3d-*` classes — plan section 07 calls for removing the
  operational parallax there while keeping the live backend-driven flow.
- `CandidateCard.jsx` and the evidence/human-review UI haven't been
  touched — plan section 08 asks for the same editorial/light visual
  integration, preserving the existing logic.
- No responsive QA pass at 1920/1440/1280/768/390/360 — this sandbox has
  no browser to verify visually.
- No WebGL fallback/performance-budget or final accessibility sweep
  beyond what already existed (`useScenePerformanceTier`,
  `:focus-visible`).

## Build verification
This sandbox has no network access, so `npm install` could not run and no
build/lint/visual check was possible here. All edits were reviewed by hand
for balanced braces/JSX and consistent import paths.

---

## Pass 2 — genuinely light dashboard + double-helix scene + parallax scope

This pass responds to explicit follow-up feedback: the dashboard's DNA
visual still sat inside a dark rectangular frame, and it read as a
labeled cross of four dots around a core rather than a DNA structure.
Scope was intentionally narrow — no other redesign, per the request to
move to browser QA after this.

**Removed the dark frame; re-lit the scene for a white canvas**
- `AgentCoreScene.jsx`'s `<Canvas>` has no background color and never
  did — the dark look came entirely from `.dna-hero-frame`'s CSS
  (`radial-gradient` dark panel). That CSS is gone; `.dna-hero-frame` is
  now just a sizing box with no border/background/shadow, so the network
  sits directly on the page's own light background.
- Because the scene's lighting/materials were originally tuned to glow
  against black, simply removing the frame would have made everything
  faint/invisible on white. Retuned in `AgentCoreScene.jsx`:
  ambient/hemisphere/point lights brightened and neutralized (no
  environment map, so geometry needs even direct light rather than
  relying on dark-background bloom); node and core base colors changed
  from near-white/mirror-metal to charcoal/mid-tone with lower metalness
  (0.8→0.25–0.35) so they don't render as flat black without an HDRI;
  node/label/line colors deepened and saturated (e.g. node active colors
  `#b6fff5`→`#0ea5b8`, `#93a7ff`→`#5b6fe0`, etc.; node label text
  `#f4f7fb`/`#7f8a9d` → `#12151c`/`#6b7488`) so everything stays legible
  against white. `PHASE_COLOR` values were deepened the same way. None
  of this touched `deriveSceneState` or the phase/activeNode mapping —
  same meanings (cyan=normal, amber=evaluating, teal=completed,
  red=error), just retuned hex/intensity for a light backdrop.

**DNA-like double-helix structure (not a labeled cross)**
- Added a purely structural `HelixBackbone` (two counter-phased spiral
  strands + periodic connecting "rungs", built with the same
  `CatmullRomLine` already used for data-flow lines) wrapped in a slow,
  self-contained `HelixSpin` rotation group. This is decorative geometry
  only — no state ties, computed once via `useMemo` — so it can't
  interact with `deriveSceneState`.
- `NODE_DEFS` positions changed from a flat top/left/right/bottom cross
  to points along that same helix (alternating strands, spiraling top to
  bottom): Protocol near the top, Patients and Evidence at the middle
  heights, Human Review near the bottom, with the existing multi-part
  Core sitting at the vertical center — the same node keys, labels,
  `direction`, and the same `FlowParticles`/line-to-core connections as
  before, just repositioned. The whole helix + core rotates slowly and
  continuously on its own (not on pointer/scroll), which is the "subtle
  internal motion, spatially stable" the acceptance test asks for.

**Parallax scope**
- Removed `usePointerParallax`/`useScrollParallax` (and the
  `data-depth`/`data-scroll-speed` attributes that drove them) from
  `TrialMindConsole.jsx` (`/trialmind`). Nothing else on that page
  changed — same live pipeline states, same `AgentCoreScene` props, same
  `hero-3d-*` classes/copy.
- The only place `usePointerParallax`/`useScrollParallax` still exist is
  the dormant, unused `AgentCoreHero.jsx` (no route renders it) — left
  in place, reserved for a possible future marketing/landing page, per
  "parallax only for the marketing/landing experience."

**Demo banner made unconditional**
- `DemoBanner.jsx` no longer calls the health-check API or hides itself;
  it always renders all three labels. This was a deliberate response to
  "keep ... permanently visible" — the previous fail-open-but-hideable
  behavior no longer applied here. No backend API or clinical logic was
  touched; this is a UI-only simplification.

**Confirmed already satisfied, no change needed**
- Cards (`.glass-card`/`.card` in `index.css`) were already flat —
  solid `var(--bg-panel)` background, 1px border, no `backdrop-filter` —
  despite the "glass" class name (a naming leftover, not an actual
  glass effect). Left as-is.
- Typography/color tokens (`--text`, `--sys-cyan/violet/green/amber/red`,
  `--accent-blue`) were already the light/near-black + restrained-accent
  palette from Pass 1; not touched again here.

**Not touched this pass, unchanged from before**
- `TrialMindConsole.jsx`'s own `.hero-3d-*` visual styling (dark
  hardcoded colors) — only its parallax was removed, per this round's
  explicit scope. A full light restyle of `/trialmind` and
  `CandidateCard.jsx` is still the flagged, not-yet-done P1 item.

## Build verification
Same constraint as Pass 1: no network access in this sandbox, so no
`npm install`/build/visual check was possible. Edits were reviewed by
hand for balanced braces/JSX, consistent imports, and preserved
`deriveSceneState`/`NODE_DEFS` key semantics. **A real browser QA pass
(as planned next) is the first actual visual verification this design
will get.**

---

## Pass 3 — final P0 polish (camera lock + hero scale), then freeze

Two narrowly-scoped fixes only, per explicit instruction not to redesign
further.

**Camera manipulation disabled**
- `AgentCoreScene.jsx`: removed the `<CameraControls>` element and its
  import entirely (rather than trying to prop-disable it), so there is no
  interactive orbit/zoom control mounted at all on the operational scene.
  The `<Canvas>`'s own fixed `camera={{ position: [0,0,5.6], fov: 42 }}`
  already looks straight at the origin by default (position on the
  camera's local +Z axis with identity rotation looks down -Z through
  the origin), so removing `CameraControls` doesn't change the framing —
  it just removes the only thing that could move it. The DNA's own
  internal motion (helix self-rotation, core pulse, node/flow animation)
  is untouched, and this is the same component used by both the
  Dashboard and `/trialmind`, so operational camera stability now holds
  in both places.

**DNA hero scale (Dashboard only)**
- `.dna-hero-frame` height: 340px → 460px on desktop, 260px → 340px at
  ≤900px, and a new 300px step at ≤480px — same responsive breakpoints
  as before, just larger at each step, so the visualization is
  proportionally bigger everywhere rather than only on desktop.
- Camera distance nudged from 6 → 5.6 (a modest, not a full re-frame) so
  the helix fills more of the taller frame. Checked against geometry:
  at fov 42 / distance 5.6 the visible vertical half-extent is ~2.15
  world units; the helix backbone's own extent is ±2.0 (its node
  positions sit within ±1.6), so there's still clearance and nothing
  should clip.
- `.dna-hero-copy` (eyebrow, title, CTA buttons) and the global
  `DemoBanner` are both unaffected by this — they're separate
  grid/layout regions, not sized off the visual column's height — so
  "Start Screening" and the demo status stay visible exactly as before.
- Did **not** touch `HELIX_TOP`/`HELIX_BOTTOM`/`HELIX_RADIUS`,
  `NODE_DEFS`, `deriveSceneState`, or any other geometry/state logic —
  scale comes from the container + a small camera-distance change only.

## Status: frozen
No further visual/redesign changes planned. Next step is browser QA and
real backend/build verification — this sandbox has no network access, so
none of the three passes here have been visually verified in an actual
browser or build.
