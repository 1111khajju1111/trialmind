import GlassCard from "../ui/GlassCard.jsx";

const STATUS_META = {
  Active: { color: "var(--accent-emerald)", pulse: true },
  Running: { color: "var(--accent-cyan)", pulse: true },
  Monitoring: { color: "var(--accent-violet)", pulse: true },
  Ready: { color: "var(--text-secondary)", pulse: false },
  Idle: { color: "var(--text-secondary)", pulse: false },
};

export default function AIAgentCard({ icon, name, status, task, lastActivity }) {
  const meta = STATUS_META[status] || STATUS_META.Ready;
  return (
    <GlassCard className="agent-card" glow="ai">
      <div className="agent-card-top">
        <span className="agent-card-icon">{icon}</span>
        <span className={`agent-card-status ${meta.pulse ? "is-pulsing" : ""}`} style={{ "--status-color": meta.color }}>
          <span className="agent-card-status-dot" />
          {status}
        </span>
      </div>
      <div className="agent-card-name">{name}</div>
      {task && <div className="agent-card-task">{task}</div>}
      {lastActivity && <div className="agent-card-activity">{lastActivity}</div>}
    </GlassCard>
  );
}
