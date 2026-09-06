import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client.js";
import DNADashboardHero from "../components/DNADashboardHero.jsx";
import KPIGrid from "../components/dashboard/KPIGrid.jsx";
import GlassCard from "../components/ui/GlassCard.jsx";
import Reveal from "../design-system/Reveal.jsx";
import TrialMindWorkspace from "../components/TrialMindWorkspace.jsx";
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
      api.getPatients(),
      api.getAlerts(),
      api.getPortfolio(),
    ])
      .then(([logRes, trialsRes, matchesRes, draftsRes, patientsRes, alertsRes, portfolioRes]) => {
        setLog(logRes.data);
        setAlerts(alertsRes.data);
        setPortfolio(portfolioRes.data);
        const matches = matchesRes.data;
        const drafts = draftsRes.data;
        setStats({
          trials: trialsRes.data.length,
          totalPatients: patientsRes.data.length,
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
    { value: stats.patientsAnalyzed, label: "Match Decisions" },
    { value: stats.potentialMatches, label: "Evidence-Backed Matches" },
    { value: stats.pendingReview, label: "Pending Review" },
    { value: log.length, label: "Audit Events" },
  ] : undefined;

  return (
    <div>
      {/* 02 -- DNA intelligence hero: one dominant visual, no parallax. */}
      <DNADashboardHero strip={heroStrip} />

      <Reveal as="div">
        <GlassCard glow="ai" style={{ marginBottom: 28, border: "2px solid var(--accent-cyan)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 11, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--accent-cyan)", fontWeight: 800 }}>AIIA Clinical Research Command Center</div>
              <h1 style={{ margin: "6px 0 4px", fontSize: "clamp(24px, 3vw, 38px)" }}>From study start to close-out</h1>
              <p className="subtitle" style={{ margin: 0 }}>CTMS operations, TrialMind intelligence, pharmacovigilance and regulatory control in one portfolio view.</p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Link style={{ padding: "9px 14px", border: "1px solid var(--border-strong)", color: "var(--text-primary)", textDecoration: "none", fontWeight: 700, fontSize: 12 }} to="/studies">Studies</Link>
              <Link style={{ padding: "9px 14px", border: "1px solid var(--border-strong)", color: "var(--text-primary)", textDecoration: "none", fontWeight: 700, fontSize: 12 }} to="/compliance">Compliance</Link>
              <Link style={{ padding: "9px 14px", border: "1px solid var(--border-strong)", color: "var(--text-primary)", textDecoration: "none", fontWeight: 700, fontSize: 12 }} to="/safety">Safety</Link>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(120px,1fr))", gap: 8, marginTop: 20 }}>
            {[
              ["01", "Protocol"], ["02", "IEC"], ["03", "CTRI"], ["04", "Sites"],
              ["05", "Recruit"], ["06", "Monitor"], ["07", "Safety"], ["08", "Close-out"]
            ].map(([n,label]) => (
              <div key={n} style={{ padding: "10px 12px", border: "1px solid var(--border-subtle)", background: "var(--surface-1)" }}>
                <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{n}</div>
                <div style={{ fontWeight: 750, marginTop: 3 }}>{label}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      </Reveal>

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
            <a
              href="#trialmind-workspace"
              className="scenario-callout-link"
              onClick={(e) => {
                e.preventDefault();
                document.getElementById("trialmind-workspace")?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              Run the matching workflow <IconChevronRight />
            </a>
          </GlassCard>
        </Reveal>
      )}

      {/* 05 -- TrialMind screening console, embedded directly here so
          there is a single dashboard that covers everything the old
          standalone /trialmind page used to (protocol upload, matching
          runs, candidate review, outreach). */}
      <TrialMindWorkspace />

      {/* 06 -- agent activity: compact status list, not five equal cards. */}
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
                {portfolio.data_quality_module_available && (
                  <div style={{ margin: "-4px 0 18px", padding: "12px 14px", border: "1px solid var(--border-subtle)", background: "var(--surface-1)" }}>
                    <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-secondary)", marginBottom: 6 }}>Data quality monitor</div>
                    <div style={{ fontSize: 12.5, color: portfolio.data_quality.open_checks ? "var(--accent-amber)" : "var(--accent-emerald)" }}>
                      {portfolio.data_quality.open_checks ? `${portfolio.data_quality.open_checks} completeness checks need attention` : "All configured completeness checks clear"}
                    </div>
                  </div>
                )}

                <div className="section-heading">
                  <span className="section-heading-icon"><IconPatients /></span> AI Recruitment Engine
                </div>
                <KPIGrid
                  items={[
                    { icon: <IconPatients />, label: "Active Trials", value: stats?.trials ?? 0, glow: "ai" },
                    { icon: <IconSearch />, label: "Match Decisions", value: stats?.patientsAnalyzed ?? 0 },
                    { icon: <IconPatients />, label: "Patient Records", value: stats?.totalPatients ?? 0 },
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
