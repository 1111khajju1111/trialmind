# TrialMind — P1 Polish Pass

Applied against the version reviewed at 9.5/10, addressing the specific
issues raised rather than introducing new visual concepts, per the review's
own "stop redesigning, start polishing" recommendation.

## 1. Semantic state colors (fixed the flagged issue)
`CandidateCard.jsx`: the "Criteria Passed" percentage's color (and its
progress bar) is now driven by `match.verdict` — ELIGIBLE → green,
POTENTIAL_MATCH / VERIFICATION_REQUIRED → amber, NOT_ELIGIBLE → red —
instead of by raw percentage thresholds. A NOT_ELIGIBLE candidate that
still passed 4/5 criteria (one disqualifying exclusion) now reads red at
80%, not green. Percentage stays a neutral fact; the verdict controls tone.

## 2. HUMAN REVIEW terminology
The 3D Agent Core's fourth node was labeled "DECISION" while every 2D
surface said "HUMAN REVIEW". Relabeled the node to **HUMAN REVIEW** (with a
smaller font size + `maxWidth` wrap so the longer label still fits the node)
so the visualization doesn't imply the AI is the one deciding.

## 3. CTA hierarchy
"Run Matching Agent" vs. "Add Trial Protocol" had equal button weight.
"Add Trial Protocol" is now a text-link-style tertiary action (underline,
muted color, no border/fill) so Run Matching Agent is unambiguously the
dominant action, per the review's note.

## 4. Accessibility
Added a global `:focus-visible` outline (cyan ring) across links, buttons,
and form controls, so keyboard users always get a visible focus indicator —
this was previously left to the browser default, which is inconsistent
across the dark theme's flat surfaces.

## 5. Performance tiers for the 3D scene
Added `useScenePerformanceTier()` (`design-system/motion.js`), a coarse
signal from `navigator.hardwareConcurrency`, `navigator.deviceMemory` (where
available), viewport width, and `prefers-reduced-motion`:
- **full** — native device pixel ratio, shadows on.
- **reduced** — DPR capped at 1, shadows off (same `<Canvas>`, cheaper to
  render) — applied automatically via the `dpr`/`shadows` props on
  `AgentCoreScene`'s `<Canvas>`.
- **static** — WebGL never mounts; both hero components
  (`AgentCoreHero.jsx`, `TrialMindConsole.jsx`) render the existing pulsing
  orb `SceneFallback` instead, so a very low-power device gets a real
  fallback rather than a struggling 3D scene.

## Not done in this pass
- The full `Surface` / `EvidenceSurface` / `DecisionSurface` component
  migration away from `GlassCard` — this is a larger refactor (component
  API + every call site) that risks exactly the kind of scope creep the
  review just recommended stopping; flagging it as the next concrete task
  rather than doing it partially.
- Full responsive QA pass (physically checking CandidateCard, the human
  review gate, the 3D scene, and pipeline chips at multiple breakpoints) —
  no real browser available in this environment to verify visually; the
  CSS these components use is already responsive-aware (existing
  `@media (max-width: 900px)` rules), but this needs an actual visual check.

## Build verification
Same constraint as before: this sandbox has no network access, so
`npm install`/`npm ci` cannot complete here regardless of the code's
correctness. All edits were checked by hand (brace/paren balance across
every touched file). Please run `cd frontend && npm ci && npm run build &&
npm run dev` locally before the demo.

## Update — one real bug found via static browser QA

I don't have a working `npm install` in this sandbox (no network), so I
couldn't run the live app. I could, however, render the *actual*
`index.css` against hand-reconstructed real markup (nav, hero/console,
pipeline chips, RunCompleteSummary, CandidateCard, human-review gate,
bottom nav) in a real headless Chromium and screenshot it at the requested
sizes: 1920×1080, 1440×900, 1280×720, 768px, 390×844, 360×800.

**Bug found and fixed:** `.bottomnav` (fixed, appears under 900px) had no
matching space reserved in `.main-content`'s bottom padding, which only
kicked in under 720px. In the 721–900px band — which includes the flagged
768px tablet width — the fixed bottom nav had nothing reserved for it and
sat on top of the last row of page content once scrolled to the bottom.
Fixed by aligning both breakpoints on 900px. Confirmed by re-rendering
768px before/after: before, the hero system-strip's last stat was covered;
after, the page ends with normal clearance below the human-review gate.

**Checked and NOT a bug**, despite how it first looked in a shrunk-down
screenshot: the pipeline chips (PROTOCOL → PATIENTS → EVIDENCE → HUMAN
REVIEW) at 360px. `flex-wrap: wrap` on `.hero-3d-console-pipeline` works as
intended — it wraps to two rows (2+2) and "HUMAN REVIEW" renders fully,
unclipped. Zoomed crop confirmed this before I trusted the first read.

**What this static render does and doesn't cover:** it's real CSS against
real markup, so genuine layout/overflow/breakpoint bugs like the one above
are trustworthy findings. It does *not* exercise the live Three.js Agent
Core canvas, real backend-driven state transitions, animation timing, or
actual click-through interaction — that part of the QA checklist (the full
RUN → ... → COMPLETE → SUMMARY → CANDIDATES pass, watching for flicker/
layout jump) still needs a real `npm run dev` session, which I can't run
here.

## Update — two P0 edge-case fixes

Verified both against the actual current source (not taken on faith) before
fixing:

1. **RunCompleteSummary skipped on zero-match runs** — confirmed real:
   it was rendered inside `{matches.length > 0 && (...)}`, so a
   successfully completed run that matched zero patients showed only the
   "No candidates were evaluated" card, no summary. Restructured
   `TrialMind.jsx` so `potential`/`excluded`/`needsReview` are computed
   once regardless of `matches.length`, `RunCompleteSummary` renders on
   `!running && lastStep === "run_completed"` alone, and the empty-state
   card renders directly underneath it when `matches.length === 0`.
   Rendered the zero-match case in the static harness to confirm: summary
   shows "1,284 Patients Screened → 0 Potential Matches → 0 Need Human
   Review", followed by the empty-state message, no candidate groups.

2. **`ERROR_STEP_NAMES` inconsistency** — confirmed real: the pipeline's
   local fallback set (used so an error step doesn't reset already-passed
   chips) only had `agent_error` / `tool_error` / `run_timeout`, while
   `hasError` and every other terminal/error set in the file
   (`TERMINAL_STEPS`, `ActionTimeline.jsx`'s `ERROR_STEPS`/`TERMINAL_STEPS`)
   already included `persistence_failed`. Added it to `ERROR_STEP_NAMES`
   so all error paths agree.

Both are one-line/small structural fixes, not new UI — design stays frozen.
