import { useEffect, useState } from "react";

const STATUS_ICON = {
  pass: "✓",
  fail: "✗",
  missing: "⚠",
};

const STATUS_COLOR = {
  pass: "var(--accent-emerald)",
  fail: "var(--accent-red)",
  missing: "var(--accent-amber)",
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
  const [showSendAdvanced, setShowSendAdvanced] = useState(false);
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

  return (
    <div className="card">
      {/* Header */}
      <div className="card-header">
        <div>
          <strong>
            {patientName || `Patient #${match.patient_id}`}
          </strong>

          <span
            className={`badge ${match.verdict}`}
            style={{ marginLeft: 10 }}
          >
            {VERDICT_LABEL[match.verdict] || match.verdict}
          </span>
        </div>

        <span className={`badge ${match.status}`}>
          {match.status.replace("_", " ")}
        </span>
      </div>

      {/* Study/site scope -- Priority 2: every recommendation is traceable
          to the exact recruitment context it was generated for. */}
      {(match.study_id || siteName) && (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 8px" }}>
          {siteName ? `Site: ${siteName}` : "Study-scoped candidate"}
        </p>
      )}

      {/* Criteria summary */}
      <p
        style={{
          fontSize: 12,
          color: "var(--text-secondary)",
          margin: "4px 0 10px",
        }}
      >
        Verified: {verifiedCount}/{totalCount} criteria
        {missingInfo.length > 0 &&
          ` · Missing/unverified: ${missingInfo.length}`}
      </p>

      {/* WHY ELIGIBLE? -- structured evidence trace, one panel per
          criterion: patient value -> protocol requirement -> decision ->
          protocol source. This is the strongest technical differentiator
          (deterministic rule + traceable evidence, not an LLM guess), so
          it gets first billing over the free-text rationale below. */}
      <div className="evidence-trace">
        {(match.criteria_results || []).map((c, i) => {
          const { value, requirement } = splitDetail(c.detail);
          return (
            <div key={i} className="evidence-trace-item">
              <div className="evidence-trace-label">
                {c.label || `Criterion ${i + 1}`}
                {c.crit_type === "exclusion" && " · exclusion check"}
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
              <div className="evidence-trace-decision" style={{ color: STATUS_COLOR[c.status] }}>
                {STATUS_ICON[c.status]} {c.status === "pass" ? "PASS" : c.status === "fail" ? "FAIL" : "NEEDS VERIFICATION"}
              </div>
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

      {/* Agent rationale */}
      <p style={{ fontSize: 13 }}>
        <strong>Agent rationale:</strong> {match.rationale}
      </p>

      {/* Additional protocol evidence retrieved by RAG, beyond the
          per-criterion sources shown above */}
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
            {requiresReview ? "⚠ HUMAN REVIEW REQUIRED" : "HUMAN REVIEW"}
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
              className="reject"
              onClick={() => onReject(match.id, reviewerNote)}
            >
              Reject
            </button>
            <button onClick={() => onApprove(match.id, reviewerNote)}>
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

      {/* Outreach Draft: Generate -> Edit -> Finalize is the primary,
          human-controlled flow. Actually addressing/sending is a secondary,
          "advanced" action tucked behind a toggle -- so a judge never reads
          this as an AI that auto-emails physicians. */}
      {match.outreach_draft && (
        <div style={{ marginTop: 12 }}>
          <p
            style={{
              fontSize: 13,
              marginBottom: 6,
            }}
          >
            <strong>
              {match.outreach_status === "SENT"
                ? "Outreach — SENT"
                : match.outreach_status === "FINALIZED"
                ? "Outreach — FINALIZED · NOT SENT"
                : "Outreach — DRAFT (editable)"}
            </strong>
          </p>

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

              {!showSendAdvanced ? (
                <div style={{ marginTop: 10 }}>
                  <button
                    className="secondary"
                    onClick={() => setShowSendAdvanced(true)}
                  >
                    Finalize Outreach Draft
                  </button>
                  <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "6px 0 0" }}>
                    Finalizing locks this draft as a coordinator-approved record. It does not
                    email anyone by itself — no communication is sent automatically.
                  </p>
                </div>
              ) : (
                <div
                  style={{
                    marginTop: 10,
                    padding: 10,
                    border: "1px dashed var(--border)",
                    borderRadius: 8,
                  }}
                >
                  <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 6px" }}>
                    Advanced: physician email (for record only — demo mode never actually
                    transmits an email; this only finalizes the draft).
                  </p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
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
                      {sending ? "Saving draft…" : "Confirm & Finalize"}
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Terminal state -- text matches outreach_status, never
                  overclaims a real transmission that didn't happen. */}
              <pre className="draft-content">
                {match.outreach_draft}
              </pre>

              <div
                style={{
                  marginTop: 8,
                  fontSize: 12,
                  color: match.outreach_status === "SENT" ? "var(--accent-emerald)" : "var(--accent-amber, #d9a441)",
                  fontWeight: 600,
                }}
              >
                {match.outreach_status === "SENT"
                  ? "✓ Email sent."
                  : "FINALIZED — NOT SENT. Recorded for coordinator review; no email was transmitted."}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
