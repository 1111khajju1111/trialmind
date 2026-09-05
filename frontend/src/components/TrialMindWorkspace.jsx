import { useEffect, useRef, useState } from "react";
import api from "../api/client.js";
import ActionTimeline from "./ActionTimeline.jsx";
import CandidateCard from "./CandidateCard.jsx";
import GlassCard from "./ui/GlassCard.jsx";
import GradientButton from "./ui/GradientButton.jsx";
import ProgressRing from "./ui/ProgressRing.jsx";
import TrialMindConsole from "./TrialMindConsole.jsx";
import RunCompleteSummary from "./RunCompleteSummary.jsx";
import { IconTrialMind } from "../design-system/icons.jsx";
import Reveal from "../design-system/Reveal.jsx";

const TERMINAL_STEPS = new Set(["run_completed", "run_timeout", "agent_error", "persistence_failed"]);
const POLL_INTERVAL_MS = 800;
const WAKE_PULSE_MS = 900;

// TrialMind's screening console, embedded directly in the Dashboard
// page (see pages/Dashboard.jsx) so there is a single dashboard that
// does everything TrialMind.jsx used to do on its own route.
export default function TrialMindWorkspace() {
  const [trials, setTrials] = useState([]);
  const [selectedTrial, setSelectedTrial] = useState("");
  const [patients, setPatients] = useState([]);
  const [matches, setMatches] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [running, setRunning] = useState(false);
  const [justStarted, setJustStarted] = useState(false);
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
    setJustStarted(true);
    setTimeout(() => setJustStarted(false), WAKE_PULSE_MS);
    setError(null);
    setTimeline([]);
    setMatches([]);
    stopPolling();

    let res;
    try {
      res = await api.startMatching(Number(selectedTrial), selectedSite ? Number(selectedSite) : null);
    } catch (e) {
      setError(extractErrorMessage(e, "Could not start the agent. Check backend logs."));
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

  // Always re-fetch scoped to the run currently on screen -- fetching the
  // unscoped, system-wide match list here was the source of "previously
  // approved candidates showing up again": every action (approve/reject,
  // generate outreach, send outreach) was refreshing with every match ever
  // created across every trial and every run, not just the ones actually
  // being reviewed right now.
  const refreshMatches = async () => {
    const m = await api.getMatches(activeRunId || undefined);
    setMatches(m.data);
  };

  // Shared helper: turns either an axios rejection (network error, or a
  // 401/403 raised by require_role() -- e.g. a session that expired mid-use)
  // or a resolved-but-{error}-shaped response into one user-facing message.
  const extractErrorMessage = (e, fallback) => {
    if (e?.response?.status === 401) {
      return "Your session has expired. Please log out and log back in.";
    }
    if (e?.response?.data?.detail) return e.response.data.detail;
    if (e?.response?.data?.error) return e.response.data.error;
    return fallback;
  };

  const decide = async (matchId, action, reviewerNote) => {
    try {
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
      await refreshMatches();
    } catch (e) {
      setError(extractErrorMessage(e, "Could not record that decision."));
    }
  };

  const generateOutreach = async (matchId) => {
    try {
      const res = await api.generateOutreach(matchId);
      if (res.data.error) {
        setError(res.data.error);
        return;
      }
      await refreshMatches();
    } catch (e) {
      setError(extractErrorMessage(e, "Could not generate the outreach draft."));
    }
  };

  const sendOutreach = async (matchId, toEmail, customDraft) => {
  try {
    const res = await api.sendOutreach(matchId, { to_email: toEmail, custom_draft: customDraft });
    if (res.data.error) {
      setError(res.data.error);
      return;
    }
    await refreshMatches();
  } catch (e) {
    setError(extractErrorMessage(e, "Failed to send outreach email."));
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
  // For the pipeline chips specifically: if the run ended on an error step
  // (agent_error / tool_error / run_timeout), fall back to the last real
  // work step so progress already confirmed by the backend still shows as
  // passed, instead of the error step resetting every chip to pending.
  const ERROR_STEP_NAMES = new Set(["agent_error", "tool_error", "run_timeout", "persistence_failed"]);
  const pipelineStep = ERROR_STEP_NAMES.has(lastStep)
    ? [...timeline].reverse().find((s) => !ERROR_STEP_NAMES.has(s.step_name))?.step_name ?? null
    : lastStep;

  // "Patients Screened" should reflect the actual search_patients result
  // population (parsed from its detail text), not matches.length -- which
  // is only the persisted PatientMatch records, i.e. a subset.
  const searchStep = timeline.find((s) => s.step_name === "search_patients");
  const screenedCount = searchStep?.detail?.match(/Found (\d+) patient/)?.[1];
  const patientsScreened = screenedCount != null ? Number(screenedCount) : matches.length;

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

  const confidencePct = currentTrial && currentTrial.criteria_count
    ? Math.round((currentTrial.machine_checkable_count / currentTrial.criteria_count) * 100)
    : 0;

  return (
    <div id="trialmind-workspace" style={{ scrollMarginTop: 88 }}>
      <div className="section-heading" style={{ marginTop: 32 }}>
        <span className="section-heading-icon"><IconTrialMind /></span> TrialMind Screening Console
      </div>
      {error && <div className="alert-box">{error}</div>}

      <TrialMindConsole
        lastStep={lastStep}
        pipelineStep={pipelineStep}
        running={running}
        hasError={hasError}
        justStarted={justStarted}
        sceneStatusLabel={sceneStatusLabel}
        sceneStepLabel={sceneStepLabel}
        currentTrial={currentTrial}
        patientCount={patients.length}
        matchCount={matches.length}
        confidencePct={confidencePct}
        onRun={runAgent}
        canRun={!!selectedTrial}
        onToggleUpload={() => setShowUpload(!showUpload)}
        showUpload={showUpload}
      />

      <div className="section-heading">
        <span className="section-heading-icon"><IconTrialMind /></span> Trials
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

      {currentTrial && (
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
            <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: 0 }}>
              This protocol isn't linked to a CTMS study, so approved candidates won't be tied to
              a study/site recruitment record. Link it to a study first if you want approvals to
              feed the recruitment funnel.
            </p>
          )}
        </GlassCard>
      )}


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

      {(() => {
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
            {/* Renders on any successful completed run, including a
                zero-match one -- the signature flow's SUMMARY step is
                part of "the agent finished", not conditional on finding
                candidates. The empty-state message right below still
                covers the zero-match case explicitly. */}
            {!running && lastStep === "run_completed" && (
              <RunCompleteSummary
                screened={patientsScreened}
                potential={potential.length}
                needsReview={needsReview.length}
              />
            )}
            {!running && timeline.length > 0 && matches.length === 0 && !error && (
              <GlassCard>
                {timeline.some(
                  (s) => s.step_name === "run_completed" && s.detail?.includes("already had an approved/rejected decision")
                )
                  ? "Every patient in this run's pool already has an approved or rejected decision on this trial from an earlier run -- nothing new to review."
                  : "No candidates were evaluated in this run."}
              </GlassCard>
            )}
            {potential.length > 0 && (
              <Reveal as="div">
                <div className="section-heading" style={{ color: "var(--accent-emerald)" }}>
                  Potential Candidates ({potential.length})
                </div>
                {potential.map(cardFor)}
              </Reveal>
            )}
            {needsReview.length > 0 && (
              <Reveal as="div" delay={60}>
                <div className="section-heading" style={{ color: "var(--accent-amber)" }}>
                  Needs Human Review ({needsReview.length})
                </div>
                {needsReview.map(cardFor)}
              </Reveal>
            )}
            {excluded.length > 0 && (
              <Reveal as="div" delay={120}>
                <div className="section-heading" style={{ color: "var(--accent-red)" }}>
                  Excluded Candidates ({excluded.length})
                </div>
                {excluded.map(cardFor)}
              </Reveal>
            )}
          </>
        );
      })()}
    </div>
  );
}