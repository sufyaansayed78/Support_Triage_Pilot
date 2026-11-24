import { useState } from "react";
import { BookOpen, Check, Copy } from "lucide-react";
import ConfidenceGauge from "./Gauge";
import { DecisionBadge } from "./Badges";
import { categoryLabel, decisionOf } from "../lib/format";

function CopyButton({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="btn-quiet"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        } catch {
          /* clipboard unavailable (insecure origin): ignore */
        }
      }}
    >
      {done ? <Check size={15} /> : <Copy size={15} />}
      {done ? "Copied" : "Copy"}
    </button>
  );
}

// The routing outcome for a ticket: decision, confidence vs threshold, why, draft and sources.
export default function TriageSummary({ result }) {
  const d = decisionOf(result.decision);
  return (
    <div className="triage">
      <div className="triage-head">
        <DecisionBadge decision={result.decision} />
        <span className="triage-category">{categoryLabel(result.category)}</span>
      </div>

      <ConfidenceGauge confidence={result.confidence} threshold={result.threshold} decision={result.decision} />

      <section className="block">
        <h3>Why this route</h3>
        <ul className="reasons">
          {result.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </section>

      {result.draft ? (
        <section className="block">
          <div className="block-head">
            <h3>Drafted reply</h3>
            <CopyButton text={result.draft} />
          </div>
          <div className="draft">{result.draft}</div>
        </section>
      ) : (
        <section className="block">
          <h3>Drafted reply</h3>
          <p className="muted">No draft was written. {d.hint}</p>
        </section>
      )}

      {result.citations?.length > 0 && (
        <section className="block">
          <h3>
            <BookOpen size={15} aria-hidden="true" /> Sources used
          </h3>
          <ul className="citations">
            {result.citations.map((c) => (
              <li key={c.chunk_id}>
                <details>
                  <summary>
                    <span className="mono">{c.source}</span>
                    <span className="score">match {c.score.toFixed(2)}</span>
                  </summary>
                  <p>{c.snippet}</p>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
