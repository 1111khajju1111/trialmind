import { useEffect, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";
import { IconRegulatory } from "../design-system/icons.jsx";
import HumanInLoopBadge from "../components/ui/HumanInLoopBadge.jsx";

const DEFAULT_SUMMARY =
  "Phase 2 trial of GLYCO-3 in 240 patients with Type 2 Diabetes over 24 weeks. " +
  "Primary endpoint: change in HbA1c from baseline. Mean reduction of 1.1% in " +
  "treatment arm vs 0.3% in placebo arm. Most common adverse events: mild " +
  "gastrointestinal discomfort (12%), headache (7%). No serious adverse events " +
  "attributed to study drug.";

export default function RegulatoryDrafting() {
  const [title, setTitle] = useState("GLYCO-3 Submission");
  const [section, setSection] = useState("CTD Module 2.5 Clinical Overview");
  const [summary, setSummary] = useState(DEFAULT_SUMMARY);
  const [drafts, setDrafts] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const loadDrafts = () => {
    api.getDrafts().then((res) => setDrafts(res.data)).catch(() => {});
  };

  useEffect(() => { loadDrafts(); }, []);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await api.createDraft({ title, section, source_summary: summary });
      loadDrafts();
    } catch (e) {
      setError("Draft generation failed. Check backend logs / API key.");
    } finally {
      setGenerating(false);
    }
  };

  const decide = async (draftId, action) => {
    await api.submitApproval({ module: "regulatory", record_id: draftId, action });
    loadDrafts();
  };

  return (
    <div>
      <h1>Regulatory Submission Drafting</h1>
      <p className="subtitle">
        Drafts are accelerants for regulatory affairs review, not final filings.
        Every draft requires human approval before it moves forward.
      </p>

      {error && <div className="alert-box">{error}</div>}

      <GlassCard glow="ai">
        <div className="card-header">
          <strong>AI Regulatory Agent</strong>
          <span className="status-badge status-badge-available">
            <span className="status-badge-dot" /> Ready
          </span>
        </div>
        <label>Submission title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label>Section</label>
        <input value={section} onChange={(e) => setSection(e.target.value)} />
        <label>Source data summary</label>
        <textarea rows={5} value={summary} onChange={(e) => setSummary(e.target.value)} />
        <GradientButton variant="ai" onClick={generate} disabled={generating}>
          {generating ? "Generating regulatory draft..." : "Generate Draft"}
        </GradientButton>
        {generating && (
          <div className="draft-progress" style={{ marginTop: 12 }}>
            <div className="draft-progress-track">
              <div className="draft-progress-fill" />
            </div>
          </div>
        )}
      </GlassCard>

      <div className="section-heading">
        <span className="section-heading-icon"><IconRegulatory /></span> Drafts &amp; Version History
      </div>

      {drafts.length === 0 && !generating && (
        <GlassCard>No drafts yet. Generate one above.</GlassCard>
      )}

      {drafts.map((d) => (
        <GlassCard key={d.id}>
          <div className="card-header">
            <strong>{d.title} — {d.section}</strong>
            <span className={`badge ${d.status}`}>
              {d.status === "pending_review" ? "✓ Draft Generated" : d.status.replace("_", " ")}
            </span>
          </div>
          <pre className="draft-content">{d.draft_content}</pre>
          {d.status === "pending_review" && (
            <div>
              <div style={{ margin: "0 0 8px" }}>
                <HumanInLoopBadge label="AI-drafted section — review before approving" />
              </div>
              <GradientButton variant="primary" onClick={() => decide(d.id, "approved")}>
                Review &amp; Submit for Approval
              </GradientButton>
              <GradientButton variant="danger" onClick={() => decide(d.id, "rejected")}>
                Reject
              </GradientButton>
            </div>
          )}
        </GlassCard>
      ))}
    </div>
  );
}
