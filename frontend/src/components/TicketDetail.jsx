import { useEffect, useState } from "react";
import { CircleAlert, X } from "lucide-react";
import { api } from "../lib/api";
import { StatusPill } from "./Badges";
import TriageSummary from "./TriageSummary";
import FeedbackForm from "./FeedbackForm";
import { fullDate } from "../lib/format";

export default function TicketDetail({ id, seed, onClose, onChanged }) {
  const [record, setRecord] = useState(seed ?? null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0); // bump to refetch after feedback
  const [sentFor, setSentFor] = useState(null); // keep the confirmation visible after the refetch

  useEffect(() => {
    let live = true;
    setError("");
    if (!seed || seed.ticket.ticket_id !== id) setRecord(null);
    api
      .getTicket(id)
      .then((r) => live && setRecord(r))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, version]);

  const t = record?.ticket;
  const r = record?.result;
  const reviewed = t?.feedback_status === "Submitted";

  return (
    <aside className="detail" aria-label="Ticket details">
      <header className="detail-head">
        <div>
          <p className="mono id">{id}</p>
          <h2>{t?.subject ?? "Loading ticket…"}</h2>
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close ticket">
          <X size={18} />
        </button>
      </header>

      {error && (
        <div className="notice bad" role="alert">
          <CircleAlert size={18} aria-hidden="true" />
          <div>{error}</div>
        </div>
      )}

      {record && (
        <div className="detail-body">
          <div className="meta">
            <StatusPill record={record} />
            <span>{fullDate(t.created_at)}</span>
            <span>via {t.channel}</span>
            {t.customer_id && <span>Customer {t.customer_id}</span>}
            {t.external_id && <span className="mono">{t.external_id}</span>}
          </div>

          <section className="block">
            <h3>Customer message</h3>
            <p className="message">{t.body}</p>
          </section>

          {r ? <TriageSummary result={r} /> : <p className="muted">This ticket has no triage result yet.</p>}

          <section className="block feedback-block">
            <h3>Agent feedback</h3>
            {!r?.draft ? (
              <p className="muted">
                There is no draft to review, so feedback isn&apos;t available. A person handles this ticket directly.
              </p>
            ) : reviewed && sentFor !== id ? (
              <div className="notice ok" role="status">
                <div>
                  <strong>Feedback sent</strong>
                  <p>An agent has already reviewed this draft.</p>
                </div>
              </div>
            ) : (
              <FeedbackForm
                key={id}
                ticketId={id}
                draft={r.draft}
                onSent={() => {
                  setSentFor(id);
                  setVersion((v) => v + 1);
                  onChanged?.();
                }}
              />
            )}
          </section>
        </div>
      )}
    </aside>
  );
}
