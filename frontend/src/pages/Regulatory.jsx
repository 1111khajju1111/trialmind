import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import KPIGrid from "../components/dashboard/KPIGrid.jsx";
import {
  IconClipboard, IconCheck, IconClock, IconMinus, IconRegulatory,
  IconCalendar, IconDot, IconAlertCircle, IconSearch,
} from "../design-system/icons.jsx";

const SEVERITY_BADGE = { overdue: "rejected", due_soon: "high" };
const TYPE_ICON = {
  milestone: <IconRegulatory />,
  safety: <IconAlertCircle />,
  monitoring: <IconSearch />,
};

function badge(map, value) {
  return <span className={`badge ${map[value] || "normal"}`}>{(value || "").replace(/_/g, " ")}</span>;
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString() : "\u2014";
}

export default function Regulatory() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getRegulatoryDashboard()
      .then((r) => setData(r.data))
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="loading">Loading...</p>;
  if (error) return <div className="alert-box">{error}</div>;
  if (!data) return null;

  const ctri = data.ctri_status_counts || {};

  return (
    <div>
      <h1>Ethics + CTRI + Regulatory Compliance</h1>
      <p className="subtitle">
        CTRI registration status, the regulatory milestone timeline (IEC submission/approval,
        CTRI registration/update, amendments, close-out), and a unified compliance alert feed
        across the whole portfolio.
      </p>

      <div className="section-heading"><span className="section-heading-icon"><IconClipboard /></span> CTRI Registration Status</div>
      <div className="kpi-grid">
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon"><IconCheck /></div>
          <div className="kpi-card-value">{ctri.registered || 0}</div>
          <div className="kpi-card-label">Registered</div>
        </GlassCard>
        <GlassCard className="kpi-card" glow={(ctri.pending || 0) > 0 ? "warning" : undefined}>
          <div className="kpi-card-icon"><IconClock /></div>
          <div className="kpi-card-value">{ctri.pending || 0}</div>
          <div className="kpi-card-label">Pending</div>
        </GlassCard>
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon"><IconMinus /></div>
          <div className="kpi-card-value">{ctri.not_registered || 0}</div>
          <div className="kpi-card-label">Not Registered</div>
        </GlassCard>
        <GlassCard className="kpi-card">
          <div className="kpi-card-icon"><IconRegulatory /></div>
          <div className="kpi-card-value">{data.amendments_logged}</div>
          <div className="kpi-card-label">Amendments Logged</div>
        </GlassCard>
      </div>

      <div className="section-heading"><span className="section-heading-icon"><IconCalendar /></span> Regulatory Milestones</div>
      <KPIGrid
        items={[
          { icon: <IconDot color="var(--accent-emerald)" />, label: "On Track", value: data.regulatory_milestones_on_track },
          {
            icon: <IconDot color="var(--accent-amber)" />, label: "Due Soon", value: data.regulatory_milestones_due_soon,
            glow: data.regulatory_milestones_due_soon > 0 ? "warning" : undefined,
          },
          {
            icon: <IconDot color="var(--accent-red)" />, label: "Overdue", value: data.regulatory_milestones_overdue,
            glow: data.regulatory_milestones_overdue > 0 ? "warning" : undefined,
          },
          { icon: <IconCheck />, label: "Completed", value: data.regulatory_milestones_completed },
        ]}
      />
      {data.deadline_disclaimer && (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "-6px 0 16px" }}>
          {data.deadline_disclaimer}
        </p>
      )}

      <div className="section-heading">
        <span className="section-heading-icon"><IconAlertCircle /></span> Compliance Alerts ({data.total_alert_count})
      </div>
      {data.alerts.length === 0 && (
        <GlassCard>No overdue or due-soon items across the portfolio right now.</GlassCard>
      )}
      {data.alerts.map((a, i) => (
        <GlassCard key={i} glow={a.severity === "overdue" ? "warning" : undefined}>
          <div className="card-header">
            <strong>{TYPE_ICON[a.type] || ""} {a.title}</strong>
            {badge(SEVERITY_BADGE, a.severity)}
          </div>
          <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "2px 0" }}>
            {a.study_code ? (
              <Link to={`/studies/${a.study_id}`} style={{ color: "var(--accent-cyan)" }}>{a.study_code}</Link>
            ) : "Unknown study"}
            {" \u00B7 "}{a.detail}
          </p>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "2px 0" }}>
            Due {fmtDate(a.due_date)}
          </p>
        </GlassCard>
      ))}
    </div>
  );
}
