import { useEffect, useRef, useState } from "react";

export default function AnimatedCounter({ value = 0, duration = 600 }) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(null);
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (reducedMotion) {
      setDisplay(value);
      return;
    }
    const start = performance.now();
    const from = 0;
    const to = Number(value) || 0;

    function tick(now) {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value, duration, reducedMotion]);

  return <span>{display}</span>;
}
