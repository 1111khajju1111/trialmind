import GlassCard from "../ui/GlassCard.jsx";
import AnimatedCounter from "../ui/AnimatedCounter.jsx";

export default function KPIGrid({ items }) {
  return (
    <div className="kpi-grid">
      {items.map((item) => (
        <GlassCard key={item.label} className="kpi-card" glow={item.glow}>
          <div className="kpi-card-icon">{item.icon}</div>
          <div className="kpi-card-value">
            <AnimatedCounter value={item.value} />
            {item.suffix || ""}
          </div>
          <div className="kpi-card-label">{item.label}</div>
          {item.trend && <div className="kpi-card-trend">{item.trend}</div>}
        </GlassCard>
      ))}
    </div>
  );
}
