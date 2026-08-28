import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client.js";
import AgentCoreHero from "../components/AgentCoreHero.jsx";
import KPIGrid from "../components/dashboard/KPIGrid.jsx";
import AIAgentCard from "../components/ai/AIAgentCard.jsx";
import GlassCard from "../components/ui/GlassCard.jsx";

export default function Dashboard() {
  const [log, setLog] = useState([]);
  const [stats, setStats] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      api.getApprovalLog(),
      api.getTrials(),
      api.getMatches(),
      api.getDrafts(),
      api.getAlerts(),
      api.getPortfolio(),
    ])
      .then(([logRes, trialsRes, matchesRes, draftsRes, alertsRes, portfolioRes]) => {
        setLog(logRes.data);
        setAlerts(alertsRes.data);
        setPortfolio(portfolioRes.data);
        const matches = matchesRes.data;
        const drafts = draftsRes.data;
        setStats({
          trials: trialsRes.data.length,
          patientsAnalyzed: matches.length,
          potentialMatches: matches.filter(
            (m) => m.verdict === "POTENTIAL_MATCH" || m.verdict === "ELIGIBLE"
          ).length,
          pendingReview:
            matches.filter((m) => m.status === "pending_review").length +
            drafts.filter((d) => d.status === "pending_review").length,
        });
      })
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  }, []);

  const agents = [
    {
      icon: "\u{1F9EC}",
      name: "Trial Extraction Agent",
      status: "Active",
      task: "Parsing eligibility criteria from protocol text",
      lastActivity: `${stats?.trials ?? 0} trials indexed`,
    },
    {
      icon: "\u{1F465}",
      name: "Patient Matching Agent",
      status: "Running",
      task: "Evaluating deterministic + AI-assisted eligibility",
      lastActivity: `${stats?.patientsAnalyzed ?? 0} candidates analyzed`,
    },
    {
      icon: "\u{1F4CB}",
      name: "Regulatory Agent",
      status: "Active",
      task: "Drafting submission sections for review",
      lastActivity: "Awaiting next request",
    },
    {
      icon: "\u{1F9EA}",
      name: "Lab Scheduling Agent",
      status: alerts.length > 0 ? "Monitoring" : "Ready",
      task: "Watching sample storage and equipment queue",
      lastActivity: `${alerts.length} active alert${alerts.length === 1 ? "" : "s"}`,
    },
    {
      icon: "\u{1F50D}",
      name: "Audit Agent",
      status: "Ready",
      task: "Standing by to trace the next run",
      lastActivity: `${log.length} logged decision${log.length === 1 ? "" : "s"}`,
    },
  ];

  return (
    <div>
      <AgentCoreHero />

      {error && <div className="alert-box">{error}</div>}
      {loading && <p className="loading">Loading...</p>}

      {alerts.length > 0 && (
        <div className="alert-box-critical">
          <span className="alert-box-critical-icon">⚠️</span>
          <div className="alert-box-critical-body">
            <div className="alert-box-critical-title">
              {alerts.length} laboratory alert{alerts.length === 1 ? "" : "s"} require attention
            </div>
            <div className="alert-box-critical-detail">{alerts[0].message}</div>
          </div>
        </div>
      )}

      {portfolio && (
        <>
          <div className="section-heading" style={{ justifyContent: "space-between", display: "flex", alignItems: "center" }}>
            <span><span className="section-heading-icon">🏥</span> Clinical Trial Portfolio</span>
            <Link to="/studies" style={{ fontSize: 12, color: "var(--accent-cyan)", fontWeight: 600 }}>
              Manage studies →
            </Link>
          </div>
          <KPIGrid
            items={[
              { icon: "\u{1F3E5}", label: "Active Studies", value: portfolio.active_studies, glow: "ai" },
              {
                icon: "\u{1F465}",
                label: "Enrollment",
                value: portfolio.total_enrolled,
                suffix: ` / ${portfolio.total_enrollment_target}`,
              },
              {
                icon: "\u{1F40C}",
                label: "Recruitment Lag",
                value: portfolio.recruitment_lag_studies,
                glow: portfolio.recruitment_lag_studies > 0 ? "warning" : undefined,
              },
              {
                icon: "\u{1F4C5}",
                label: "Pending IEC/CTRI Actions",
                value: portfolio.pending_iec_ctri_actions,
                glow: portfolio.pending_iec_ctri_actions > 0 ? "warning" : undefined,
              },
              {
                icon: "\u26A0\uFE0F",
                label: "Open Protocol Deviations",
                value: portfolio.open_protocol_deviations,
                glow: portfolio.open_protocol_deviations > 0 ? "warning" : undefined,
              },
              {
                icon: "\u{1F50D}",
                label: "Overdue Monitoring Visits",
                value: portfolio.overdue_monitoring_visits,
                glow: portfolio.overdue_monitoring_visits > 0 ? "warning" : undefined,
              },
            ]}
          />

          <div className="section-heading" style={{ justifyContent: "space-between", display: "flex", alignItems: "center" }}>
            <span><span className="section-heading-icon">🩺</span> Pharmacovigilance</span>
            <Link to="/safety" style={{ fontSize: 12, color: "var(--accent-cyan)", fontWeight: 600 }}>
              Open safety dashboard →
            </Link>
          </div>
          {portfolio.safety_module_available ? (
            <KPIGrid
              items={[
                { icon: "\u{1FA79}", label: "Adverse Events (AE)", value: portfolio.ae_count },
                {
                  icon: "\u{1F6A8}",
                  label: "Serious Adverse Events (SAE)",
                  value: portfolio.sae_count,
                  glow: portfolio.sae_count > 0 ? "warning" : undefined,
                },
                { icon: "\u{1F4C2}", label: "Open Safety Cases", value: portfolio.open_safety_cases },
                {
                  icon: "\u23F0",
                  label: "Overdue Safety Reports",
                  value: portfolio.overdue_safety_reports,
                  glow: portfolio.overdue_safety_reports > 0 ? "warning" : undefined,
                },
              ]}
            />
          ) : (
            <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "-6px 0 16px" }}>
              Pharmacovigilance KPIs not available yet.
            </p>
          )}
          {!portfolio.data_quality_module_available && (
            <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "-6px 0 16px" }}>
              Data-quality query counts arrive with a later priority — not shown yet rather than
              shown as a misleading zero.
            </p>
          )}
        </>
      )}

      <div className="section-heading">
        <span className="section-heading-icon">🧬</span> AI Recruitment Engine
      </div>
      {stats && (
        <KPIGrid
          items={[
            { icon: "\u{1F9EC}", label: "Active Trials", value: stats.trials, glow: "ai" },
            { icon: "\u{1F465}", label: "Patients Analyzed", value: stats.patientsAnalyzed },
            { icon: "\u2705", label: "Potential / Eligible Matches", value: stats.potentialMatches, glow: "success" },
            { icon: "\u23F3", label: "Pending Review", value: stats.pendingReview, glow: stats.pendingReview > 0 ? "warning" : undefined },
          ]}
        />
      )}

      <div className="section-heading">
        <span className="section-heading-icon">🤖</span> AI Agents
      </div>
      <div className="agent-grid">
        {agents.map((a) => (
          <AIAgentCard key={a.name} {...a} />
        ))}
      </div>

      <div className="section-heading" style={{ justifyContent: "space-between", display: "flex", alignItems: "center" }}>
        <span><span className="section-heading-icon">🕒</span> Recent Activity</span>
        <Link to="/audit" style={{ fontSize: 12, color: "var(--accent-cyan)", fontWeight: 600 }}>
          View full audit trail →
        </Link>
      </div>

      {!loading && !error && log.length === 0 && (
        <GlassCard>
          No approvals or rejections yet. Run the matching agent on the
          Trial Matching page, then approve or reject a candidate to see
          activity here.
        </GlassCard>
      )}

      {log.map((entry) => (
        <GlassCard key={entry.id}>
          <div className="card-header">
            <strong>{entry.module.replace("_", " ")}</strong>
            <span className={`badge ${entry.action}`}>{entry.action}</span>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)" }}>
            Record #{entry.record_id} · {entry.actor} · {new Date(entry.timestamp).toLocaleString()}
          </p>
        </GlassCard>
      ))}
    </div>
  );
}
