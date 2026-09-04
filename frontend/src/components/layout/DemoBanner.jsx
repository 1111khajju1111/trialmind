/**
 * This turn's brief is explicit: keep the demo-environment notice
 * PERMANENTLY visible, so it no longer depends on a backend health
 * check that could hide it -- it always renders, on every demo-facing
 * page, as a light, high-contrast, text-first status strip (not
 * color-only) with all three required labels.
 */
export default function DemoBanner() {
  return (
    <div className="demo-banner" role="status" aria-label="Demo environment notice">
      <span className="demo-banner-pill">
        <span className="demo-banner-dot" aria-hidden="true" />
        DEMO ENVIRONMENT
      </span>
      <span className="demo-banner-sep" aria-hidden="true">·</span>
      <span className="demo-banner-secondary">SYNTHETIC DATA</span>
      <span className="demo-banner-sep" aria-hidden="true">·</span>
      <span className="demo-banner-tertiary">NOT FOR CLINICAL DECISION-MAKING</span>
    </div>
  );
}
