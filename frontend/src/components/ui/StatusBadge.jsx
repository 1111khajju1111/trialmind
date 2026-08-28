export default function StatusBadge({ status, children, className = "" }) {
  return (
    <span className={`status-badge status-badge-${status} ${className}`}>
      <span className="status-badge-dot" />
      {children}
    </span>
  );
}
