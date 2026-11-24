import { useCallback, useEffect, useMemo, useState } from "react";
import { Inbox, RefreshCw, Search } from "lucide-react";
import { api } from "../lib/api";
import { categoryLabel, decisionOf, pct, shortId, timeAgo } from "../lib/format";
import { StatusPill } from "../components/Badges";
import TicketDetail from "../components/TicketDetail";

// Each tab is backed by one backend endpoint.
const TABS = [
  { key: "all", label: "All tickets", path: "GET /v1/tickets", call: api.listAll, empty: "No tickets yet. Create one to see it here." },
  { key: "drafted", label: "AI drafted", path: "GET /v1/tickets/AI_drafted_tickets", call: api.listDrafted, empty: "No drafts are waiting for review." },
  { key: "escalated", label: "Needs a person", path: "GET /v1/tickets/Escalated_tickets", call: api.listEscalated, empty: "Nothing is waiting for a person." },
];

function Row({ record, active, onOpen }) {
  const { ticket, result } = record;
  const tone = decisionOf(result?.decision).tone;
  return (
    <li>
      <button type="button" className={`row tone-${tone}${active ? " active" : ""}`} onClick={onOpen} aria-current={active}>
        <span className="stripe" aria-hidden="true" />
        <span className="row-main">
          <span className="row-subject">{ticket.subject}</span>
          <span className="row-body">{ticket.body}</span>
        </span>
        <span className="row-cat">
          <span>{result ? categoryLabel(result.category) : "–"}</span>
          {result && (
            <span className="mini" title={`Confidence ${pct(result.confidence)}`}>
              <span className={`mini-fill tone-${tone}`} style={{ width: `${result.confidence * 100}%` }} />
              <span className="mini-num">{pct(result.confidence)}</span>
            </span>
          )}
        </span>
        <span className="row-end">
          <StatusPill record={record} />
          <span className="when">
            <span className="mono">{shortId(ticket.ticket_id)}</span> · {timeAgo(ticket.created_at)}
          </span>
        </span>
      </button>
    </li>
  );
}

export default function Queue({ selectedId, go, refreshKey }) {
  const [tab, setTab] = useState("all");
  const [data, setData] = useState({}); // key -> {rows, error}
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const settled = await Promise.allSettled(TABS.map((t) => t.call()));
    const next = {};
    settled.forEach((s, i) => {
      next[TABS[i].key] =
        s.status === "fulfilled" ? { rows: s.value, error: "" } : { rows: [], error: s.reason?.message || "Failed to load" };
    });
    setData(next);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && selectedId && go("/queue");
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, go]);

  const current = TABS.find((t) => t.key === tab);
  const entry = data[tab] ?? { rows: [], error: "" };

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return entry.rows;
    return entry.rows.filter(({ ticket, result }) =>
      [ticket.subject, ticket.body, ticket.ticket_id, ticket.customer_id, result?.category, categoryLabel(result?.category)]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle)),
    );
  }, [entry.rows, q]);

  const seed = useMemo(
    () => Object.values(data).flatMap((d) => d.rows).find((r) => r.ticket.ticket_id === selectedId),
    [data, selectedId],
  );

  return (
    <>
      <header className="page-head with-action">
        <div>
          <h1>Queue</h1>
          <p>Review drafts, and see what needs a person.</p>
        </div>
        <button type="button" className="btn-secondary" onClick={load} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} aria-hidden="true" /> Refresh
        </button>
      </header>

      <div className={`queue-layout${selectedId ? " has-detail" : ""}`}>
        <section className="list-col">
          <div className="tabs" role="tablist" aria-label="Ticket lists">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={tab === t.key}
                className={`tab${tab === t.key ? " on" : ""}`}
                onClick={() => setTab(t.key)}
              >
                {t.label}
                <span className="count">{data[t.key] && !data[t.key].error ? data[t.key].rows.length : "–"}</span>
              </button>
            ))}
          </div>

          <div className="list-tools">
            <label className="search">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search subject, message, category or ID"
                aria-label="Search tickets"
              />
            </label>
            <code className="endpoint">{current.path}</code>
          </div>

          {entry.error ? (
            <div className="notice bad" role="alert">
              <div>
                <strong>Couldn&apos;t load this list</strong>
                <p>{entry.error}</p>
              </div>
              <button type="button" className="btn-secondary" onClick={load}>
                Try again
              </button>
            </div>
          ) : loading && !data[tab] ? (
            <ul className="rows" aria-busy="true">
              {[0, 1, 2].map((i) => (
                <li key={i} className="skeleton" />
              ))}
            </ul>
          ) : rows.length === 0 ? (
            <div className="empty">
              <Inbox size={28} aria-hidden="true" />
              <p>{q ? "No tickets match your search." : current.empty}</p>
              {!q && tab === "all" && (
                <button type="button" className="btn-secondary" onClick={() => go("/new")}>
                  Create a ticket
                </button>
              )}
            </div>
          ) : (
            <ul className="rows">
              {rows.map((r) => (
                <Row
                  key={r.ticket.ticket_id}
                  record={r}
                  active={r.ticket.ticket_id === selectedId}
                  onOpen={() => go(`/queue/${r.ticket.ticket_id}`)}
                />
              ))}
            </ul>
          )}
        </section>

        {selectedId && (
          <>
            <div className="scrim" onClick={() => go("/queue")} aria-hidden="true" />
            <TicketDetail
              key={selectedId}
              id={selectedId}
              seed={seed}
              onClose={() => go("/queue")}
              onChanged={load}
            />
          </>
        )}
      </div>
    </>
  );
}
