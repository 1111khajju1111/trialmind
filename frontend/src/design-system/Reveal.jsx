import { useReveal } from "./motion.js";

/**
 * Wraps a section so it fades/slides into place the first time it crosses
 * into view, then stays. Use around KPI grids, agent rosters, and
 * candidate result groups so the page reads as a scroll-choreographed
 * narrative instead of everything being present at once.
 */
export default function Reveal({ as: Tag = "div", delay = 0, className = "", children, ...rest }) {
  const ref = useReveal();
  return (
    <Tag
      ref={ref}
      className={`tm-reveal-wrap ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
      {...rest}
    >
      {children}
    </Tag>
  );
}
