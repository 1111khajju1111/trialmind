import AnimatedCounter from "./ui/AnimatedCounter.jsx";
import Reveal from "../design-system/Reveal.jsx";

/**
 * The payoff of the TrialMind "signature moment": once a run completes,
 * this shows before the candidate lists do -- screened -> potential ->
 * needs-review, each an animated count-up, so the result of the run reads
 * as one connected story rather than three separate section headings.
 */
export default function RunCompleteSummary({ screened, potential, needsReview }) {
  return (
    <Reveal as="div">
      <div className="tm-run-complete">
        <div className="tm-run-complete-label">Screening Complete</div>

        <div className="tm-run-complete-stat">
          <div className="tm-run-complete-value"><AnimatedCounter value={screened} /></div>
          <div className="tm-run-complete-caption">Patients Screened</div>
        </div>
        <div className="tm-run-complete-connector">→</div>
        <div className="tm-run-complete-stat is-potential">
          <div className="tm-run-complete-value"><AnimatedCounter value={potential} duration={750} /></div>
          <div className="tm-run-complete-caption">Potential Matches</div>
        </div>
        <div className="tm-run-complete-connector">→</div>
        <div className="tm-run-complete-stat is-review">
          <div className="tm-run-complete-value"><AnimatedCounter value={needsReview} duration={900} /></div>
          <div className="tm-run-complete-caption">Need Human Review</div>
        </div>
      </div>
    </Reveal>
  );
}
