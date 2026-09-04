import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client.js";
import DNADashboardHero from "../components/DNADashboardHero.jsx";
import KPIGrid from "../components/dashboard/KPIGrid.jsx";
import GlassCard from "../components/ui/GlassCard.jsx";
import Reveal from "../design-system/Reveal.jsx";
import {
  IconStudies, IconPatients, IconRegulatory, IconLab, IconAudit,
  IconTrend, IconWarning, IconClock, IconCheck, IconBell,
  IconFolder, IconSafety, IconSearch, IconChevronRight, IconRadar, IconCompliance,
} from "../design-system/icons.jsx";

const AGENT_STATUS_META = {
  Active: "var(--accent-emerald)",
  Running: "var(--accent-cyan)",
  Monitoring: "var(--accent-violet)",
  Ready: "var(--text-secondary)",
  Idle: "var(--text-secondary)",
};

export default function Dashboard() {
  const [log, setLog] = useState([]);
  const [stats, setStats] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modulesOpen, setModulesOpen] = useState(false);

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
      icon: <IconStudies />,
      name: "Trial Extraction Agent",
      status: "Active",
      task: "Parsing eligibility criteria from protocol text",
      lastActivity: `${stats?.trials ?? 0} trials indexed`,
    },
    {
      icon: <IconPatients />,
      name: "Patient Matching Agent",
      status: "Running",
      task: "Evaluating deterministic + AI-assisted eligibility",
      lastActivity: `${stats?.patientsAnalyzed ?? 0} candidates analyzed`,
    },
    {
      icon: <IconRegulatory />,
      name: "Regulatory Agent",
      status: "Active",
      task: "Drafting submission sections for review",
      lastActivity: "Awaiting next request",
    },
    {
      icon: <IconLab />,
      name: "Lab Scheduling Agent",
      status: alerts.length > 0 ? "Monitoring" : "Ready",
      task: "Watching sample storage and equipment queue",
      lastActivity: `${alerts.length} active alert${alerts.length === 1 ? "" : "s"}`,
    },
    {
      icon: <IconAudit />,
      name: "Audit Agent",
      status: "Ready",
      task: "Standing by to trace the next run",
      lastActivity: `${log.length} logged decision${log.length === 1 ? "" : "s"}`,
    },
  ];

  // System strip in the DNA hero: the handful of numbers that answer
  // "what is happening right now" before the user scrolls at all.
  const heroStrip = stats && portfolio ? [
    { value: portfolio.active_studies, label: "Active Studies" },
    { value: stats.patientsAnalyzed, label: "Candidates Screened" },
    { value: stats.potentialMatches, label: "Evidence-Backed Matches" },
    { value: stats.pendingReview, label: "Pending Review" },
    { value: log.length, label: "Audit Events" },
  ] : undefined;

  return (
    <div>
      {/* 02 -- DNA intelligence hero: one dominant visual, no parallax. */}
      <DNADashboardHero strip={heroStrip} />

      {error && <div className="alert-box">{error}</div>}
      {loading && <p className="loading">Loading...</p>}

      {/* 03 -- Control Tower: the single always-visible screen a study
          director glances at, per the SIH26046 Control Tower requirement.
          Deliberately NOT inside the collapsible "Operational Modules"
          accordion below -- these six numbers are the ones that matter
          before anything else on this page. */}
      {portfolio && (
        <Reveal as="div">
          <div className="section-heading">
            <span className="section-heading-icon"><IconRadar /></span> Control Tower
          </div>
          <KPIGrid
            items={[
              { icon: <IconStudies />, label: "Active Trials", value: portfolio.active_studies, glow: "ai" },
              {
                icon: <IconPatients />, label: "Enrollment",
                value: portfolio.total_enrolled, suffix: ` / ${portfolio.total_enrollment_target}`,
              },
              {
                icon: <IconSafety />, label: "AE / SAE",
                value: portfolio.ae_count, suffix: ` AE / ${portfolio.sae_count} SAE`,
                glow: portfolio.sae_count > 0 ? "warning" : undefined,
              },
              {
                icon: <IconRadar />, label: "Open Safety Signals",
                value: portfolio.open_safety_signals,
                glow: portfolio.open_safety_signals > 0 ? "warning" : undefined,
              },
              {
                icon: <IconCompliance />, label: "Regulatory Alerts",
                value: portfolio.regulatory_alert_count,
                glow: portfolio.regulatory_alert_count > 0 ? "warning" : undefined,
              },
              {
                icon: <IconSearch />, label: "Monitoring Alerts",
                value: portfolio.monitoring_alert_count,
                glow: portfolio.monitoring_alert_count > 0 ? "warning" : undefined,
              },
            ]}
          />
        </Reveal>
      )}

      {alerts.length > 0 && (
        <div className="alert-box-critical" style={{ marginBottom: 28 }}>
          <span className="alert-box-critical-icon"><IconWarning /></span>
          <div className="alert-box-critical-body">
            <div className="alert-box-critical-title">
              {alerts.length} laboratory alert{alerts.length === 1 ? "" : "s"} require attention
            </div>
            <div className="alert-box-critical-detail">{alerts[0].message}</div>
          </div>
        </div>
      )}

      {/* 04 -- active study / demo scenario: the actual workflow to try. */}
      {portfolio && (
        <Reveal as="div">
          <GlassCard className="scenario-callout" style={{ marginBottom: 40 }}>
            <div className="scenario-callout-eyebrow">ACTIVE DEMO SCENARIO</div>
            <div className="scenario-callout-title">
              {portfolio.active_studies} active {portfolio.active_studies === 1 ? "study" : "studies"},
              {" "}{stats?.pendingReview ?? 0} candidates waiting on a human decision
            </div>
            <Link to="/trialmind" className="scenario-callout-link">
              Run the matching workflow <IconChevronRight />
            </Link>
          </GlassCard>
        </Reveal>
      )}

      {/* 05 -- agent activity: compact status list, not five equal cards. */}
      <Reveal>
        <div className="section-heading">
          <span className="section-heading-icon"><IconTrend /></span> Agent Activity
        </div>
        <div className="agent-activity-list">
          {agents.map((a) => (
            <div className="agent-activity-row" key={a.name}>
              <span className="agent-activity-icon">{a.icon}</span>
              <span className="agent-activity-name">{a.name}</span>
              <span className="agent-activity-task">{a.task}</span>
              <span
                className={`agent-activity-status ${["Active", "Running", "Monitoring"].includes(a.status) ? "is-pulsing" : ""}`}
                style={{ "--status-color": AGENT_STATUS_META[a.status] }}
              >
                <span className="agent-activity-status-dot" />
                {a.status}
              </span>
            </div>
          ))}
        </div>
      </Reveal>

      {/* 06 -- operational modules: collapsed/secondary by default. */}
      {portfolio && (
        <Reveal delay={60}>
          <div style={{ marginTop: 32 }}>
            <button
              type="button"
              className="operational-modules-toggle"
              aria-expanded={modulesOpen}
              onClick={() => setModulesOpen((v) => !v)}
            >
              <span className="section-heading-icon"><IconFolder /></span>
              Operational Modules -- Portfolio &amp; Pharmacovigilance
              <span className="operational-modules-toggle-chevron"><IconChevronRight style={{ transform: "rotate(90deg)" }} /></span>
            </button>

            {modulesOpen && (
              <div className="operational-modules-body">
                <div className="section-heading" style={{ justifyContent: "space-between", display: "flex", alignItems: "center" }}>
                  <span><span className="section-heading-icon"><IconStudies /></span> Clinical Trial Portfolio</span>
                  <Link to="/studies" className="section-heading-link">Manage studies →</Link>
                </div>
                <KPIGrid
                  items={[
                    { icon: <IconStudies />, label: "Active Studies", value: portfolio.active_studies, glow: "ai" },
                    {
                      icon: <IconPatients />,
                      label: "Enrollment",
                      value: portfolio.total_enrolled,
                      suffix: ` / ${portfolio.total_enrollment_target}`,
                    },
                    {
                      icon: <IconClock />,
                      label: "Recruitment Lag",
                      value: portfolio.recruitment_lag_studies,
                      glow: portfolio.recruitment_lag_studies > 0 ? "warning" : undefined,
                    },
                    {
                      icon: <IconFolder />,
                      label: "Pending IEC/CTRI Actions",
                      value: portfolio.pending_iec_ctri_actions,
                      glow: portfolio.pending_iec_ctri_actions > 0 ? "warning" : undefined,
                    },
                    {
                      icon: <IconWarning />,
                      label: "Open Protocol Deviations",
                      value: portfolio.open_protocol_deviations,
                      glow: portfolio.open_protocol_deviations > 0 ? "warning" : undefined,
                    },
                    {
                      icon: <IconSearch />,
                      label: "Overdue Monitoring Visits",
                      value: portfolio.overdue_monitoring_visits,
                      glow: portfolio.overdue_monitoring_visits > 0 ? "warning" : undefined,
                    },
                  ]}
                />

                <div className="section-heading" style={{ justifyContent: "space-between", display: "flex", alignItems: "center" }}>
                  <span><span className="section-heading-icon"><IconSafety /></span> Pharmacovigilance</span>
                  <Link to="/safety" className="section-heading-link">Open safety dashboard →</Link>
                </div>
                {portfolio.safety_module_available ? (
                  <KPIGrid
                    items={[
                      { icon: <IconSafety />, label: "Adverse Events (AE)", value: portfolio.ae_count },
                      {
                        icon: <IconBell />,
                        label: "Serious Adverse Events (SAE)",
                        value: portfolio.sae_count,
                        glow: portfolio.sae_count > 0 ? "warning" : undefined,
                      },
                      { icon: <IconFolder />, label: "Open Safety Cases", value: portfolio.open_safety_cases },
                      {
                        icon: <IconClock />,
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
                    Data-quality query counts arrive with a later priority -- not shown yet rather than
                    shown as a misleading zero.
                  </p>
                )}

                <div className="section-heading">
                  <span className="section-heading-icon"><IconPatients /></span> AI Recruitment Engine
                </div>
                <KPIGrid
                  items={[
                    { icon: <IconPatients />, label: "Active Trials", value: stats?.trials ?? 0, glow: "ai" },
                    { icon: <IconSearch />, label: "Patients Analyzed", value: stats?.patientsAnalyzed ?? 0 },
                    { icon: <IconCheck />, label: "Potential / Eligible Matches", value: stats?.potentialMatches ?? 0, glow: "success" },
                    { icon: <IconClock />, label: "Pending Review", value: stats?.pendingReview ?? 0, glow: (stats?.pendingReview ?? 0) > 0 ? "warning" : undefined },
                  ]}
                />
              </div>
            )}
          </div>
        </Reveal>
      )}

      {/* 07 -- recent activity: audit trail preview. */}
      <div className="section-heading" style={{ justifyContent: "space-between", display: "flex", alignItems: "center", marginTop: 32 }}>
        <span><span className="section-heading-icon"><IconClock /></span> Recent Activity</span>
        <Link to="/audit" className="section-heading-link">View full audit trail →</Link>
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
