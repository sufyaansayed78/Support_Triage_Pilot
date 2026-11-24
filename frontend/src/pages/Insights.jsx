import { useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import { categoryLabel, pct } from "../lib/format";

const RANGES = [
  { days: 1, label: "24 hours" },
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
];

function Split({ s }) {
  if (!s.total) return <div className="split-bar empty-bar" />;
  return (
    <div className="split-bar" role="img" aria-label={`${s.accept} accepted, ${s.edit} edited, ${s.reject} rejected`}>
      <span className="bar-accept" style={{ flexGrow: s.accept }} />
      <span className="bar-edit" style={{ flexGrow: s.edit }} />
      <span className="bar-reject" style={{ flexGrow: s.reject }} />
    </div>
  );
}

export default function Insights({ go, refreshKey }) {
  const [days, setDays] = useState(7);
  const [stats, setStats] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setError("");
    Promise.all([api.feedbackStats(days), api.policy()])
      .then(([s, p]) => {
        if (!live) return;
        setStats(s);
        setPolicy(p);
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [days, refreshKey]);

  const overall = stats?.overall;
  const cats = stats ? Object.entries(stats.by_category) : [];

  return (
    <>
      <header className="page-head with-action">
        <div>
          <h1>Insights</h1>
          <p>How often agents accept, edit or reject the drafts.</p>
        </div>
        <div className="range" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r.days} type="button" className={days === r.days ? "on" : ""} onClick={() => setDays(r.days)}>
              {r.label}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <div className="notice bad" role="alert">
          <div>{error}</div>
        </div>
      )}

      <div className="insights">
        <section className="panel">
          <h2>Agent feedback</h2>
          {!overall ? (
            <p className="muted">Loading…</p>
          ) : overall.total === 0 ? (
            <div className="empty compact">
              <p>No feedback in this period. Review a draft in the queue to start the loop.</p>
              <button type="button" className="btn-secondary" onClick={() => go("/queue")}>
                Open the queue
              </button>
            </div>
          ) : (
            <>
              <Split s={overall} />
              <dl className="ledger">
                <div><dt><i className="sw bar-accept" /> Accepted</dt><dd>{overall.accept}</dd></div>
                <div><dt><i className="sw bar-edit" /> Edited</dt><dd>{overall.edit}</dd></div>
                <div><dt><i className="sw bar-reject" /> Rejected</dt><dd>{overall.reject}</dd></div>
              </dl>
              <p className="summary-line">
                Agents accepted <strong>{pct(overall.acceptance_rate)}</strong> of drafts as written and used{" "}
                <strong>{pct(overall.usable_rate)}</strong> after editing, across {overall.total} reviews.
              </p>

              <h3 className="sub">By category</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Category</th>
                    <th scope="col" className="num">Reviews</th>
                    <th scope="col">Split</th>
                    <th scope="col" className="num">Accepted</th>
                  </tr>
                </thead>
                <tbody>
                  {cats.map(([cat, s]) => (
                    <tr key={cat}>
                      <th scope="row">{categoryLabel(cat)}</th>
                      <td className="num">{s.total}</td>
                      <td className="bar-cell"><Split s={s} /></td>
                      <td className="num">{pct(s.acceptance_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>

        <section className="panel">
          <h2>Routing policy</h2>
          {!policy ? (
            <p className="muted">Loading…</p>
          ) : (
            <>
              <dl className="ledger stacked">
                <div>
                  <dt>Acceptance threshold</dt>
                  <dd>{pct(policy.acceptance_threshold)}</dd>
                </div>
                <div>
                  <dt>Minimum grounding score</dt>
                  <dd>{policy.min_grounding_score.toFixed(2)}</dd>
                </div>
              </dl>
              <p className="muted">
                Below the threshold a ticket goes to human triage. These categories are always escalated, whatever the
                confidence:
              </p>
              <ul className="chips">
                {policy.never_auto_respond.map((c) => (
                  <li key={c}>
                    <ShieldAlert size={14} aria-hidden="true" /> {categoryLabel(c)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </>
  );
}
