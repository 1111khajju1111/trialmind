import { useEffect, useState } from "react";
import { IconCheck, IconCross, IconWarning } from "./../design-system/icons.jsx";
import HumanInLoopBadge from "./ui/HumanInLoopBadge.jsx";

const STATUS_ICON = {
  pass: <IconCheck />,
  fail: <IconCross />,
  missing: <IconWarning />,
};

const VERDICT_LABEL = {
  ELIGIBLE: "Eligible",
  NOT_ELIGIBLE: "Not Eligible",
  POTENTIAL_MATCH: "Potential Match",
  VERIFICATION_REQUIRED: "Verification Required",
};

// The deterministic engine's `detail` string is already formatted like
// "Age: 54 years (required >= 18 years)" -- split it back into a patient
// value and a protocol requirement so the "WHY ELIGIBLE?" panel can show
// them as two distinct rows instead of one run-on sentence.
function splitDetail(detail) {
  if (!detail) return { value: null, requirement: null };
  const match = detail.match(/^(.*?)\s*\(required (.*)\)$/);
  if (!match) return { value: detail, requirement: null };
  return { value: match[1], requirement: match[2] };
}

export default function CandidateCard({
  match,
  patientName,
  siteName,
  onApprove,
  onReject,
  onGenerateOutreach,
  onSendOutreach,
}) {
  const [emailTo, setEmailTo] = useState("");
  const [sending, setSending] = useState(false);
  const [editedDraft, setEditedDraft] = useState(match.outreach_draft || "");
  const [reviewerNote, setReviewerNote] = useState("");

  useEffect(() => {
    setEditedDraft(match.outreach_draft || "");
  }, [match.outreach_draft]);

  const verifiedCount =
    match.criteria_results?.filter((c) => c.status === "pass").length || 0;

  const totalCount = match.criteria_results?.length || 0;

  const missingInfo = match.missing_info || [];
  const evidence = match.evidence || [];

  const handleSend = async () => {
    if (!emailTo || !onSendOutreach) return;
    setSending(true);
    try {
      await onSendOutreach(match.id, emailTo, editedDraft);
    } finally {
      setSending(false);
    }
  };

  const requiresReview = match.verdict === "POTENTIAL_MATCH" || match.verdict === "VERIFICATION_REQUIRED";
  const isPendingDecision = match.status === "pending_review" && match.verdict !== "NOT_ELIGIBLE";

  // The percentage shown is always derived from real criteria_results --
  // never a fabricated "confidence" score the backend doesn't compute.
  // Labeled "CRITERIA PASSED" throughout rather than "eligibility
  // confidence" so it can't be misread as an AI certainty score.
  //
  // Color is driven by the verdict, not the raw percentage: 4/5 criteria
  // passed is NOT necessarily "mostly eligible" if the one failed
  // criterion was a disqualifying exclusion. The clinician's verdict
  // already accounts for that, so the tone (green/amber/red) always
  // reflects match.verdict -- the percentage stays a neutral fact next
  // to it, never the thing coloring the decision.
  const criteriaPct = totalCount > 0 ? Math.round((verifiedCount / totalCount) * 100) : null;
  const verdictTone =
    match.verdict === "ELIGIBLE" ? "is-eligible" :
    match.verdict === "NOT_ELIGIBLE" ? "is-low" :
    "is-partial"; // POTENTIAL_MATCH, VERIFICATION_REQUIRED
  const barClass = criteriaPct == null ? "" : verdictTone;
  const matchIdLabel = `MATCH / ${String(match.id).padStart(4, "0")}`;

  return (
    <div className="card candidate-card">
      {/* Header -- who, and where this candidate stands right now */}
      <div className="candidate-card-header">
        <div className="candidate-card-idline">
          <span className="candidate-card-match-id">{matchIdLabel}</span>
          <span className={`badge ${match.status}`}>{match.status.replace("_", " ")}</span>
        </div>
        <div className="candidate-card-name">{patientName || `Patient #${match.patient_id}`}</div>
        <div className="candidate-card-meta">
          <span className={`badge ${match.verdict}`}>{VERDICT_LABEL[match.verdict] || match.verdict}</span>
          {(match.study_id || siteName) && <span>{siteName ? `Site: ${siteName}` : "Study-scoped candidate"}</span>}
        </div>
      </div>

      {/* Eligibility panel -- the visual anchor. See it -> then inspect
          why -> then decide, instead of having to read every criterion
          just to find out where this candidate stands. */}
      <div className="eligibility-panel">
        <div className={`eligibility-panel-value ${criteriaPct == null ? "is-empty" : barClass}`}>
          {criteriaPct == null ? "—" : `${criteriaPct}%`}
        </div>
        <div className="eligibility-panel-label">Criteria Passed</div>
        {totalCount > 0 && (
          <div className="eligibility-panel-bar">
            <div className={`eligibility-panel-bar-fill ${barClass}`} style={{ width: `${criteriaPct}%` }} />
          </div>
        )}
        <div className="eligibility-panel-fraction">
          {verifiedCount} / {totalCount} criteria passed
          {missingInfo.length > 0 && ` · ${missingInfo.length} unverified`}
        </div>
      </div>

      {/* WHY ELIGIBLE? -- structured evidence trace, one panel per
          criterion: patient value -> protocol requirement -> decision ->
          protocol source. This is the strongest technical differentiator
          (deterministic rule + traceable evidence, not an LLM guess), so
          it gets first billing over the free-text rationale below. */}
      <div className="mc-section-heading">Eligibility Checks</div>
      <div className="evidence-trace">
        {(match.criteria_results || []).map((c, i) => {
          const { value, requirement } = splitDetail(c.detail);
          return (
            <div key={i} className="evidence-trace-item">
              <div className="evidence-trace-item-row">
                <div className="evidence-trace-label" style={{ marginBottom: 0 }}>
                  {c.label || `Criterion ${i + 1}`}
                  {c.crit_type === "exclusion" && " · exclusion check"}
                </div>
                <span className={`evidence-trace-pill ${c.status}`}>
                  {STATUS_ICON[c.status]} {c.status === "pass" ? "PASS" : c.status === "fail" ? "FAIL" : "REVIEW"}
                </span>
              </div>
              {value && (
                <div className="evidence-trace-row">
                  <span className="evidence-trace-row-label">Patient value</span>
                  <span>{value}</span>
                </div>
              )}
              {requirement && (
                <div className="evidence-trace-row">
                  <span className="evidence-trace-row-label">Protocol requirement</span>
                  <span>{requirement}</span>
                </div>
              )}
              {!value && !requirement && (
                <div className="evidence-trace-row">
                  <span>{c.detail}</span>
                </div>
              )}
              {c.source_text && (
                <div className="evidence-trace-source">Protocol: "{c.source_text}"</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Missing information */}
      {missingInfo.length > 0 && (
        <div className="alert-box">
          Requires human verification: {missingInfo.join(", ")}
        </div>
      )}

      {/* WHY THIS DECISION? -- agent rationale + any additional protocol
          evidence retrieved by RAG, beyond the per-criterion sources
          shown above. */}
      <div className="mc-section-heading">Why This Decision?</div>
      <p style={{ fontSize: 13, margin: "0 0 8px" }}>{match.rationale}</p>

      {evidence.length > 0 ? (
        <details style={{ fontSize: 12, marginBottom: 10 }}>
          <summary
            style={{
              cursor: "pointer",
              color: "var(--accent-cyan)",
            }}
          >
            Additional protocol evidence ({evidence.length} source
            {evidence.length > 1 ? "s" : ""})
          </summary>

          {evidence.map((e, i) => (
            <div
              key={i}
              style={{
                background: "var(--bg-secondary)",
                padding: 8,
                borderRadius: 6,
                marginTop: 6,
              }}
            >
              <div
                style={{
                  color: "var(--text-muted)",
                  fontSize: 11,
                }}
              >
                chunk #{e.chunk_id} · relevance: {e.relevance}
              </div>

              <div>{e.chunk_text}</div>
            </div>
          ))}
        </details>
      ) : (
        <p
          style={{
            fontSize: 12,
            color: "var(--text-muted)",
            fontStyle: "italic",
          }}
        >
          No additional protocol evidence found beyond the per-criterion sources above.
        </p>
      )}

      {/* Human Review gate -- deliberately the visually dominant element
          for anything not already a clean ELIGIBLE pass, so it reads as a
          safety gate rather than a formality: AI recommends, a human
          decides. */}
      {match.status === "pending_review" && match.verdict === "NOT_ELIGIBLE" && (
        <p
          style={{
            fontSize: 12.5,
            color: "var(--text-muted)",
            fontStyle: "italic",
            margin: "8px 0 0",
          }}
        >
          This candidate does not meet trial criteria and cannot be approved for outreach.
        </p>
      )}
      {isPendingDecision && (
        <div className="human-review-gate">
          <div className="human-review-gate-title">
            {requiresReview ? "HUMAN REVIEW REQUIRED" : "HUMAN REVIEW"}
          </div>
          <div style={{ margin: "2px 0 8px" }}>
            <HumanInLoopBadge label="AI-assisted eligibility check — human decides" />
          </div>
          <div className="human-review-gate-summary">
            <div className="human-review-gate-stat">
              <div className="human-review-gate-stat-value">{VERDICT_LABEL[match.verdict] || match.verdict}</div>
              <div className="human-review-gate-stat-label">AI recommendation</div>
            </div>
            <div className="human-review-gate-stat">
              <div className="human-review-gate-stat-value">{verifiedCount} / {totalCount}</div>
              <div className="human-review-gate-stat-label">Criteria pass</div>
            </div>
            <div className="human-review-gate-stat">
              <div className="human-review-gate-stat-value">{evidence.length}</div>
              <div className="human-review-gate-stat-label">Evidence sources</div>
            </div>
          </div>
          <p style={{ fontSize: 11.5, color: "var(--text-muted)", textAlign: "center", margin: "0 0 10px" }}>
            The AI does not make the final decision. A coordinator must approve or reject.
          </p>
          <input
            type="text"
            placeholder="Optional reviewer note (recorded in audit trail)"
            value={reviewerNote}
            onChange={(e) => setReviewerNote(e.target.value)}
            style={{ width: "100%", fontSize: 12.5, marginBottom: 8 }}
          />
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button
              className="tm-decisive tm-decisive-reject"
              onClick={() => onReject(match.id, reviewerNote)}
            >
              Reject
            </button>
            <button
              className="tm-decisive tm-decisive-approve"
              onClick={() => onApprove(match.id, reviewerNote)}
            >
              Approve
            </button>
          </div>
        </div>
      )}

      {/* Generate outreach */}
      {match.status === "approved" && !match.outreach_draft && (
        <button
          className="secondary"
          onClick={() => onGenerateOutreach(match.id)}
        >
          Generate Outreach Draft
        </button>
      )}

      {/* Outreach Draft: Generate -> Edit -> Send. A coordinator can still
          review and edit the AI-drafted text, but there's no separate
          "finalize, but don't actually send" holding step anymore --
          clicking Send addresses the email and transmits it via Resend
          in one action (see /patients/{id}/send-outreach). */}
      {match.outreach_draft && (
        <div style={{ marginTop: 12 }}>
          <p
            style={{
              fontSize: 13,
              marginBottom: 6,
            }}
          >
            <strong>
              {match.outreach_status === "SENT" ? "Outreach — SENT" : "Outreach — DRAFT (editable)"}
            </strong>
          </p>
          {!match.outreach_sent && (
            <div style={{ margin: "-2px 0 8px" }}>
              <HumanInLoopBadge label="AI-drafted email — review, edit if needed, then send" />
            </div>
          )}

          {!match.outreach_sent ? (
            <>
              {/* Editable draft */}
              <textarea
                rows={12}
                value={editedDraft}
                onChange={(e) => setEditedDraft(e.target.value)}
                style={{
                  width: "100%",
                  fontFamily: "monospace",
                  fontSize: 13,
                  lineHeight: 1.4,
                  padding: 10,
                  borderRadius: 6,
                  background: "var(--bg-secondary)",
                  color: "var(--text)",
                  border: "1px solid var(--border)",
                  boxSizing: "border-box",
                  resize: "vertical",
                }}
              />

              <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <input
                  type="email"
                  placeholder="physician@hospital.com"
                  value={emailTo}
                  onChange={(e) => setEmailTo(e.target.value)}
                  style={{ flex: 1, minWidth: 180, fontSize: 13 }}
                />
                <button
                  className="primary"
                  disabled={!emailTo.trim() || !editedDraft.trim() || sending}
                  onClick={handleSend}
                >
                  {sending ? "Sending via Resend…" : "Send Email"}
                </button>
              </div>
              <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "6px 0 0" }}>
                Sends immediately via Resend once you click Send — there's no additional
                verification step after this.
              </p>
            </>
          ) : (
            <>
              <pre className="draft-content">
                {match.outreach_draft}
              </pre>

              <div
                style={{
                  marginTop: 8,
                  fontSize: 12,
                  color: "var(--accent-emerald)",
                  fontWeight: 600,
                }}
              >
                ✓ Email sent via Resend.
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
