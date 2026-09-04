import { useEffect, useRef } from "react";

function prefersReducedMotion() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Pointer-driven depth parallax for a container. Elements inside the
 * container opt in with `data-depth="fg" | "mid" | "bg"`, which map to
 * roughly 8px / 4px / 1.5px of travel — matching the amplitude the design
 * brief calls for (foreground 6-10px, midground 3-5px, background 1-2px).
 * Every animation frame writes CSS custom properties instead of React
 * state, so this never re-renders the tree on mousemove.
 */
const DEPTH_PX = { fg: 8, mid: 4, bg: 1.5 };

export function usePointerParallax() {
  const containerRef = useRef(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || prefersReducedMotion()) return;

    const targets = Array.from(el.querySelectorAll("[data-depth]"));
    if (targets.length === 0) return;

    let raf = null;
    let px = 0;
    let py = 0;

    function apply() {
      targets.forEach((t) => {
        const amp = DEPTH_PX[t.dataset.depth] ?? 0;
        t.style.transform = `translate3d(${px * amp}px, ${py * amp}px, 0)`;
      });
      raf = null;
    }

    function onMove(e) {
      const rect = el.getBoundingClientRect();
      px = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      py = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
      if (!raf) raf = requestAnimationFrame(apply);
    }

    function onLeave() {
      px = 0;
      py = 0;
      if (!raf) raf = requestAnimationFrame(apply);
    }

    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerleave", onLeave);
    return () => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerleave", onLeave);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return containerRef;
}

/**
 * Scroll-linked parallax for a section. Elements opt in with
 * `data-scroll-speed`, a small float (e.g. 0.06 for a slow background,
 * 0.14 for the 3D scene, 0.22 for foreground labels) — amplitude stays
 * restrained per the motion spec, and everything is driven by an
 * IntersectionObserver + scroll listener pair scoped to just this
 * section (not a global scroll handler).
 */
export function useScrollParallax() {
  const containerRef = useRef(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || prefersReducedMotion()) return;

    const targets = Array.from(el.querySelectorAll("[data-scroll-speed]"));
    if (targets.length === 0) return;

    let ticking = false;
    let inView = true;

    function apply() {
      const rect = el.getBoundingClientRect();
      const mid = rect.top + rect.height / 2 - window.innerHeight / 2;
      targets.forEach((t) => {
        const speed = parseFloat(t.dataset.scrollSpeed) || 0;
        t.style.transform = `translate3d(0, ${(-mid * speed).toFixed(1)}px, 0)`;
      });
      ticking = false;
    }

    function onScroll() {
      if (!inView || ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    }

    const io = new IntersectionObserver(
      ([entry]) => {
        inView = entry.isIntersecting;
        if (inView) onScroll();
      },
      { threshold: 0 }
    );
    io.observe(el);

    window.addEventListener("scroll", onScroll, { passive: true });
    apply();
    return () => {
      window.removeEventListener("scroll", onScroll);
      io.disconnect();
    };
  }, []);

  return containerRef;
}

/**
 * Coarse device/performance tier for the 3D Agent Core scene (P1 polish:
 * "desktop = full 3D, mobile/low-power = reduced 3D, very low-power =
 * static fallback"). Deliberately simple signals only — this isn't meant
 * to be a precise GPU benchmark, just enough to avoid mounting WebGL on
 * devices that clearly can't afford it.
 */
export function getScenePerformanceTier() {
  if (typeof window === "undefined") return "full";
  if (prefersReducedMotion()) return "static";
  const cores = navigator.hardwareConcurrency || 8;
  const mem = navigator.deviceMemory; // Chrome/Android only; undefined elsewhere
  if (cores <= 2 || (mem && mem <= 2)) return "static";
  if (cores <= 4 || window.innerWidth < 720) return "reduced";
  return "full";
}

export function useScenePerformanceTier() {
  const ref = useRef(typeof window === "undefined" ? "full" : getScenePerformanceTier());
  return ref.current;
}

/**
 * Progressive reveal-on-scroll for a section: starts hidden/offset,
 * animates in once it crosses into the viewport, then stays put (a
 * decision moment shouldn't jitter back out of view while someone reads
 * it). Reduced-motion users get the static, fully-visible end state
 * immediately with no animation frame at all.
 */
export function useReveal(options = {}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (prefersReducedMotion()) {
      el.classList.add("tm-reveal-visible");
      return;
    }

    el.classList.add("tm-reveal");
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("tm-reveal-visible");
          io.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px", ...options }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return ref;
}
