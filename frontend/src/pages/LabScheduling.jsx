import { useEffect, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import { IconWarning, IconFlask, IconMicroscope } from "../design-system/icons.jsx";

export default function LabScheduling() {
  const [samples, setSamples] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [equipment, setEquipment] = useState([]);
  const [error, setError] = useState(null);

  const load = () => {
    Promise.all([api.getSamples(), api.getAlerts(), api.getEquipment()])
      .then(([s, a, e]) => {
        setSamples(s.data);
        setAlerts(a.data);
        setEquipment(e.data);
      })
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."));
  };

  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1>Lab Equipment &amp; Sample Scheduling</h1>
      <p className="subtitle">
        Samples are auto-prioritized by urgency and storage breach status.
        Equipment availability updates the queue in real time.
      </p>

      {error && <div className="alert-box">{error}</div>}

      {alerts.map((a) => (
        <div className="alert-box-critical" key={a.sample_id}>
          <span className="alert-box-critical-icon"><IconWarning /></span>
          <div className="alert-box-critical-body">
            <div className="alert-box-critical-title">Storage Breach — Sample #{a.sample_id}</div>
            <div className="alert-box-critical-detail">{a.message}</div>
          </div>
          <GradientButton variant="danger" onClick={load}>
            Resolve Issue
          </GradientButton>
        </div>
      ))}

      <div className="section-heading">
        <span className="section-heading-icon"><IconFlask /></span> Equipment Status
      </div>
      <div className="agent-grid" style={{ marginBottom: 20 }}>
        {equipment.map((e) => (
          <GlassCard key={e.id}>
            <div className="card-header">
              <strong>{e.name}</strong>
              <StatusBadge status={e.status === "available" ? "available" : "booked"}>
                {e.status}
              </StatusBadge>
            </div>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0 }}>
              {e.equipment_type}
            </p>
            <div className="draft-progress-track" style={{ marginTop: 12 }}>
              <div
                style={{
                  height: "100%",
                  borderRadius: 999,
                  width: e.status === "available" ? "18%" : "82%",
                  background: e.status === "available" ? "var(--gradient-success)" : "var(--gradient-warning)",
                }}
              />
            </div>
          </GlassCard>
        ))}
      </div>

      <div className="section-heading">
        <span className="section-heading-icon"><IconMicroscope /></span> Samples
      </div>
      {samples.map((s) => (
        <GlassCard key={s.id} glow={s.breach_alert ? "warning" : undefined}>
          <div className="card-header">
            <strong>{s.label}</strong>
            <span className={`badge ${s.priority}`}>{s.priority}</span>
          </div>
          <p style={{ fontSize: 13, margin: "4px 0", color: "var(--text-secondary)" }}>
            Storage: {s.storage_temp_c}°C (required {s.required_temp_c}°C)
          </p>
          {s.scheduled_time && (
            <p style={{ fontSize: 13, margin: "4px 0", color: "var(--text-secondary)" }}>
              Scheduled: {new Date(s.scheduled_time).toLocaleString()}
            </p>
          )}
          {s.breach_alert && (
            <p style={{ color: "var(--accent-red)", fontSize: 13, fontWeight: 600, margin: "8px 0 0" }}>
              <IconWarning style={{ marginRight: 4, verticalAlign: "-0.15em" }} />Storage breach detected
            </p>
          )}
        </GlassCard>
      ))}
    </div>
  );
}
