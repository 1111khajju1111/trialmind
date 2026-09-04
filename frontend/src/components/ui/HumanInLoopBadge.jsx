// Priority 2 SIH polish: a single, consistent visual marker for "this
// content was produced with AI assistance and a human must review/approve
// it before it takes effect" -- used everywhere the app surfaces an
// AI-assisted output (eligibility verdicts, outreach drafts, regulatory
// drafts) so a judge/reviewer never has to guess which parts of the app
// are AI-assisted vs. deterministic. Deliberately a lightweight inline
// pill, not a full gate -- the human-review-gate in CandidateCard.jsx
// remains the actual approve/reject workflow for the matching flow; this
// badge is for surfacing the same principle everywhere else AI output
// appears without a full gate of its own.
export default function HumanInLoopBadge({ label = "AI-assisted — human review required", style }) {
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "2px 9px", borderRadius: 999, fontSize: 10.5, fontWeight: 700,
        letterSpacing: 0.2, textTransform: "uppercase",
        color: "var(--accent-violet, var(--accent-blue))",
        border: "1px solid var(--accent-violet, var(--accent-blue))",
        background: "color-mix(in srgb, var(--accent-violet, var(--accent-blue)) 10%, transparent)",
        ...style,
      }}
    >
      🤖 {label}
    </span>
  );
}
