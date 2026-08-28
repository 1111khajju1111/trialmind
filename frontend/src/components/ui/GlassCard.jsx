export default function GlassCard({ children, className = "", glow, style, ...rest }) {
  return (
    <div
      className={`glass-card ${glow ? `glass-card-glow glass-card-glow-${glow}` : ""} ${className}`}
      style={style}
      {...rest}
    >
      {children}
    </div>
  );
}
