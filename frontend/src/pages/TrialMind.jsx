import { useEffect, useRef, useState, Suspense } from "react";
import api from "../api/client.js";
import ActionTimeline from "../components/ActionTimeline.jsx";
import CandidateCard from "../components/CandidateCard.jsx";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";
import ProgressRing from "../components/ui/ProgressRing.jsx";
import AgentCoreScene from "../components/AgentCoreScene.jsx";

const TERMINAL_STEPS = new Set(["run_completed", "run_timeout", "agent_error", "persistence_failed"]);
const POLL_INTERVAL_MS = 800;

export default function TrialMind() {
  const [trials, setTrials] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState("");
  const [patients, setPatients] = useState([]);
  const [matches, setMatches] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [running, setRunning] = useState(false);
  const [activeRunId, setActiveRunId] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const [showUpload, setShowUpload] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCondition, setNewCondition] = useState("");
  const [newProtocolText, setNewProtocolText] = useState("");
  const [pdfFile, setPdfFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  // Priority 2: study/site scoping for matching runs.
  const [studies, setStudies] = useState([]);
  const [uploadStudyId, setUploadStudyId] = useState(""); // study to link a new protocol to
  const [sites, setSites] = useState([]);                 // sites of the selected trial's linked study
  const [selectedSite, setSelectedSite] = useState("");   // "" = whole study, no site filter

  const loadTrials = () => {
    api.getTrials().then((res) => {
      setTrials(res.data);
      if (res.data.length && !selectedTrial) setSelectedTrial(res.data[0].id);
    }).catch(() => setError("Could not reach backend. Check VITE_API_URL."));
  };

  useEffect(() => {
    loadTrials();
    api.getPatients().then((res) => setPatients(res.data)).catch(() => {});
    api.getStudies().then((res) => setStudies(res.data)).catch(() => {});
    return () => clearInterval(pollRef.current);
  }, []);

  const currentTrial = trials.find((t) => String(t.id) === String(selectedTrial));

  // Whenever the selected trial's linked study changes, load that study's
  // sites so the coordinator can optionally scope the run to one of them.
  useEffect(() => {
    setSelectedSite("");
    if (currentTrial?.study_id) {
      api.getSites(currentTrial.study_id).then((res) => setSites(res.data)).catch(() => setSites([]));
    } else {
      setSites([]);
    }
  }, [currentTrial?.study_id]);

  const patientName = (id) => patients.find((p) => p.id === id)?.name;
  const siteName = (id) => sites.find((s) => String(s.id) === String(id))?.institution;

  const stopPolling = () => {
    clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const runAgent = async () => {
    if (!selectedTrial) return;
    setRunning(true);
    setError(null);
    setTimeline([]);
    setMatches([]);
    stopPolling();

    let res;
    try {
      res = await api.startMatching(Number(selectedTrial), selectedSite ? Number(selectedSite) : null);
    } catch (e) {
      setError("Could not start the agent. Check backend logs.");
      setRunning(false);
      return;
    }
    if (res.data.error) {
      setError(res.data.error);
      setRunning(false);
      return;
    }

    const runId = res.data.run_id;
    setActiveRunId(runId);

    pollRef.current = setInterval(async () => {
      try {
        const t = await api.getTimeline(runId);
        setTimeline(t.data);
        const finished = t.data.some((step) => TERMINAL_STEPS.has(step.step_name));
        if (finished) {
          stopPolling();
          setRunning(false);
          const errored = t.data.some((step) =>
            step.step_name === "agent_error" || step.step_name === "run_timeout" || step.step_name === "persistence_failed"
          );
          if (errored) {
            const errStep = t.data.find((s) =>
              s.step_name === "agent_error" || s.step_name === "run_timeout" || s.step_name === "persistence_failed"
            );
            setError(errStep?.detail || "Agent run did not complete successfully.");
          } else {
            const m = await api.getMatches(runId);
            setMatches(m.data);
          }
        }
      } catch (e) {
        stopPolling();
        setRunning(false);
        setError("Lost connection while polling agent progress.");
      }
    }, POLL_INTERVAL_MS);
  };

  const decide = async (matchId, action, reviewerNote) => {
    const res = await api.submitApproval({
      module: "patient_matching",
      record_id: matchId,
      action,
      reviewer_note: reviewerNote || undefined,
    });
    if (res.data.error) {
      setError(res.data.error);
      return;
    }
    const m = await api.getMatches();
    setMatches(m.data);
  };

  const generateOutreach = async (matchId) => {
    const res = await api.generateOutreach(matchId);
    if (res.data.error) {
      setError(res.data.error);
      return;
    }
    const m = await api.getMatches();
    setMatches(m.data);
  };

  const sendOutreach = async (matchId, toEmail, customDraft) => {
  try {
    const res = await api.sendOutreach(matchId, { to_email: toEmail, custom_draft: customDraft });
    if (res.data.error) {
      setError(res.data.error);
      return;
    }
    const m = await api.getMatches();
    setMatches(m.data);
  } catch (e) {
    setError("Failed to send outreach email.");
  }
};

  // ---------- UPDATED: supports both text and PDF, and optional study link ----------
  const submitProtocol = async () => {
    if (!newName.trim() || !newCondition.trim()) {
      setError("Trial name and condition are required.");
      return;
    }
    if (!pdfFile && !newProtocolText.trim()) {
      setError("Provide either a PDF file or protocol text.");
      return;
    }

    setUploading(true);
    setError(null);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("name", newName.trim());
      formData.append("condition", newCondition.trim());
      if (uploadStudyId) formData.append("study_id", uploadStudyId);

      if (pdfFile) {
        formData.append("file", pdfFile);
      } else {
        formData.append("protocol_text", newProtocolText);
      }

      const res = await api.uploadProtocol(formData);   // must send FormData

      if (res.data.error) {
        setError(res.data.error);
        return;
      }

      setUploadResult(res.data);
      setNewName("");
      setNewCondition("");
      setNewProtocolText("");
      setPdfFile(null);
      setUploadStudyId("");
      loadTrials();
    } catch (e) {
      console.error(e);
      setError("Protocol upload failed. Check backend logs.");
    } finally {
      setUploading(false);
    }
  };

  const lastStep = timeline.length > 0 ? timeline[timeline.length - 1].step_name : null;
  const hasError = timeline.some((s) =>
    s.step_name === "agent_error" || s.step_name === "run_timeout" || s.step_name === "persistence_failed"
  );
  const sceneStatusLabel = hasError
    ? "AGENT ERROR"
    : running
    ? "AGENT ACTIVE"
    : lastStep === "run_completed"
    ? "RUN COMPLETE"
    : "AGENT IDLE";
  const sceneStepLabel = lastStep
    ? lastStep.replace(/_/g, " ")
    : "select a trial and start a run";

  // Studies that don't yet have a linked protocol -- offered when uploading
  // a new one, since a study can only have one linked trial.
  const linkedStudyIds = new Set(trials.map((t) => t.study_id).filter(Boolean));
  const linkableStudies = studies.filter((s) => !linkedStudyIds.has(s.id));

  return (
    <div>
      <div className="trialmind-hero">
        <div className="trialmind-hero-kicker">TRIALMIND</div>
        <h1 className="trialmind-hero-title">Autonomous Recruitment Engine</h1>
        <p className="subtitle">
          Protocol → AI Agent → Deterministic Eligibility → Evidence → Human Approval → Outreach Draft → Audit.
          Deterministic rules decide; the agent retrieves evidence and explains its reasoning;
          a coordinator approves before anything reaches a physician.
        </p>
      </div>

      {error && <div className="alert-box">{error}</div>}

      <div className="agent-core-frame">
        <div className="agent-live-scene">
          <Suspense fallback={null}>
            <AgentCoreScene lastStep={lastStep} running={running} hasError={hasError} />
          </Suspense>
          <div className="agent-live-scene-label">
            <strong style={{ color: hasError ? "#ff8a8a" : undefined }}>{sceneStatusLabel}</strong>
            <span>{sceneStepLabel}</span>
          </div>
        </div>
        <div className="agent-core-pipeline">
          <span className={lastStep === "protocol_loaded" || running ? "pipeline-step is-passed" : "pipeline-step"}>PROTOCOL</span>
          <span className="pipeline-arrow">→</span>
          <span className={["search_patients", "evaluate_eligibility"].includes(lastStep) ? "pipeline-step is-active" : "pipeline-step is-passed"}>PATIENTS</span>
          <span className="pipeline-arrow">→</span>
          <span className={["retrieve_evidence", "evidence_retrieved"].includes(lastStep) ? "pipeline-step is-active" : "pipeline-step"}>EVIDENCE</span>
          <span className="pipeline-arrow">↓</span>
          <span className={lastStep === "run_completed" ? "pipeline-step is-active" : "pipeline-step"}>HUMAN REVIEW</span>
        </div>
      </div>

      <div className="section-heading">
        <span className="section-heading-icon">🧬</span> Trials
      </div>
      <div className="agent-grid" style={{ marginBottom: 20 }}>
        {trials.map((t) => (
          <GlassCard
            key={t.id}
            glow={String(t.id) === String(selectedTrial) ? "ai" : undefined}
            onClick={() => !running && setSelectedTrial(String(t.id))}
            style={{
              cursor: running ? "default" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: 14,
              outline: String(t.id) === String(selectedTrial) ? "1px solid var(--accent-violet)" : "none",
            }}
          >
            <ProgressRing
              value={(t.machine_checkable_count / Math.max(1, t.criteria_count)) * 100}
              size={52}
              gradientId={`ring-${t.id}`}
            />
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{t.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{t.condition}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                {t.machine_checkable_count}/{t.criteria_count} criteria machine-checkable
              </div>
              <div style={{ fontSize: 11, marginTop: 2 }}>
                {t.study_id ? (
                  <span className="badge approved" style={{ fontSize: 10 }}>
                    Study: {t.study_code || `#${t.study_id}`}
                  </span>
                ) : (
                  <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
                    Not linked to a study
                  </span>
                )}
              </div>
            </div>
          </GlassCard>
        ))}
      </div>

      <GlassCard>
        {currentTrial?.study_id && sites.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12 }}>
              Site to record approved candidates against (optional)
            </label>
            <select value={selectedSite} onChange={(e) => setSelectedSite(e.target.value)} disabled={running}>
              <option value="">Unassigned / decide per candidate later</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>{s.institution} ({s.site_code || `#${s.id}`})</option>
              ))}
            </select>
            <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "4px 0 0" }}>
              The AI searches the full patient directory by condition, as always. This only
              sets which site a candidate is enrolled under once a coordinator approves them.
            </p>
          </div>
        )}
        {currentTrial && !currentTrial.study_id && (
          <p style={{ fontSize: 11.5, color: "var(--text-muted)", marginBottom: 10 }}>
            This protocol isn't linked to a CTMS study, so approved candidates won't be tied to
            a study/site recruitment record. Link it to a study first if you want approvals to
            feed the recruitment funnel.
          </p>
        )}
        <GradientButton variant="ai" onClick={runAgent} disabled={running || !selectedTrial}>
          {running ? "Agent running..." : "Run Matching Agent"}
        </GradientButton>
        <GradientButton variant="secondary" onClick={() => setShowUpload(!showUpload)} disabled={running}>
          {showUpload ? "Cancel" : "Add Trial Protocol"}
        </GradientButton>
      </GlassCard>

      {showUpload && (
        <GlassCard>
          <strong>Add Trial Protocol</strong>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 12 }}>
            Upload a PDF or paste the eligibility criteria text. The matching agent extracts
            machine-checkable rules where confident and flags the rest for manual verification.
          </p>

          <label>Trial name</label>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. GLYCO-4 Trial"
          />

          <label>Condition (must match patient records, e.g. "Type 2 Diabetes")</label>
          <input
            value={newCondition}
            onChange={(e) => setNewCondition(e.target.value)}
          />

          <label style={{ marginTop: 10 }}>Link to CTMS study (optional)</label>
          <select value={uploadStudyId} onChange={(e) => setUploadStudyId(e.target.value)}>
            <option value="">Don't link yet (standalone protocol)</option>
            {linkableStudies.map((s) => (
              <option key={s.id} value={s.id}>{s.title} ({s.study_code})</option>
            ))}
          </select>

          {/* PDF upload */}
          <label style={{ marginTop: 10 }}>Upload PDF Protocol (optional)</label>
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
            style={{ fontSize: 13 }}
          />
          {pdfFile && (
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
              Selected: {pdfFile.name}
            </div>
          )}

          {/* Text paste (disabled when PDF is selected) */}
          <label style={{ marginTop: 10 }}>Or paste protocol text</label>
          <textarea
            rows={8}
            value={newProtocolText}
            onChange={(e) => setNewProtocolText(e.target.value)}
            placeholder="Paste the eligibility criteria section of the protocol here..."
            disabled={!!pdfFile}
          />

          <GradientButton variant="primary" onClick={submitProtocol} disabled={uploading}>
            {uploading ? "Extracting criteria..." : "Extract Criteria & Ingest"}
          </GradientButton>

          {uploadResult && (
            <p style={{ fontSize: 13, marginTop: 10 }}>
              Extracted <strong>{uploadResult.criteria_count}</strong> criteria —
              {" "}{uploadResult.machine_checkable_count} machine-checkable,
              {" "}{uploadResult.verification_required_count} require manual verification.
              Chunked into {uploadResult.chunk_count} sections for evidence retrieval.
              {uploadResult.study_id ? " Linked to the selected study." : ""}
            </p>
          )}
        </GlassCard>
      )}

      {activeRunId && (timeline.length > 0 || running) && (
        <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "0 0 6px", letterSpacing: "0.03em" }}>
          RUN ID: <code>{activeRunId}</code>
        </p>
      )}
      <ActionTimeline steps={timeline} running={running} />

      {!running && timeline.length > 0 && matches.length === 0 && !error && (
        <GlassCard>No candidates were evaluated in this run.</GlassCard>
      )}

      {matches.length > 0 && (() => {
        const potential = matches.filter((m) => ["ELIGIBLE", "POTENTIAL_MATCH"].includes(m.verdict) && m.status !== "rejected");
        const excluded = matches.filter((m) => m.verdict === "NOT_ELIGIBLE");
        const needsReview = matches.filter((m) => m.verdict === "VERIFICATION_REQUIRED" && !potential.includes(m));
        const cardFor = (m) => (
  <CandidateCard
    key={m.id}
    match={m}
    patientName={patientName(m.patient_id)}
    siteName={siteName(m.site_id)}
    onApprove={(id, note) => decide(id, "approved", note)}
    onReject={(id, note) => decide(id, "rejected", note)}
    onGenerateOutreach={generateOutreach}
    onSendOutreach={sendOutreach}
  />
);
        return (
          <>
            {potential.length > 0 && (
              <div>
                <div className="section-heading" style={{ color: "var(--accent-emerald)" }}>
                  Potential Candidates ({potential.length})
                </div>
                {potential.map(cardFor)}
              </div>
            )}
            {needsReview.length > 0 && (
              <div>
                <div className="section-heading" style={{ color: "var(--accent-amber)" }}>
                  Needs Human Review ({needsReview.length})
                </div>
                {needsReview.map(cardFor)}
              </div>
            )}
            {excluded.length > 0 && (
              <div>
                <div className="section-heading" style={{ color: "var(--accent-red)" }}>
                  Excluded Candidates ({excluded.length})
                </div>
                {excluded.map(cardFor)}
              </div>
            )}
          </>
        );
      })()}
    </div>
  );
}