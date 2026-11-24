import { useEffect, useState } from "react";
import { decisionOf, pct } from "../lib/format";

// The one memorable element: where the classifier's confidence landed relative to the acceptance threshold.
export default function ConfidenceGauge({ confidence = 0, threshold = 0.75, decision }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(confidence));
    return () => cancelAnimationFrame(id);
  }, [confidence]);

  const tone = decisionOf(decision).tone;
  const tickLeft = Math.min(Math.max(threshold, 0), 1) * 100;

  return (
    <div
      className="gauge"
      role="img"
      aria-label={`Confidence ${pct(confidence)}. Acceptance threshold ${pct(threshold)}.`}
    >
      <div className="gauge-track">
        <div className={`gauge-fill tone-${tone}`} style={{ width: `${Math.min(shown, 1) * 100}%` }} />
        <div className="gauge-tick" style={{ left: `${tickLeft}%` }} />
      </div>
      <div className="gauge-legend">
        <span>
          Confidence <strong>{pct(confidence)}</strong>
        </span>
        <span className="gauge-threshold" style={{ left: `${Math.min(Math.max(tickLeft, 14), 86)}%` }}>
          Threshold {pct(threshold)}
        </span>
      </div>
      {decision === "escalate" && (
        <p className="gauge-note">Confidence is ignored for never-auto-respond categories.</p>
      )}
    </div>
  );
}
