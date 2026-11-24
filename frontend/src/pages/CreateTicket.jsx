import { useState } from "react";
import { ArrowRight, CircleAlert, FilePlus2 } from "lucide-react";
import { api } from "../lib/api";
import { DECISIONS, SAMPLES, shortId } from "../lib/format";
import TriageSummary from "../components/TriageSummary";

const EMPTY = { subject: "", body: "", customer_id: "", channel: "web", external_id: "" };

function Legend() {
  return (
    <div className="legend">
      <h2>How a ticket is routed</h2>
      <p className="muted">Every new ticket lands in one of three places.</p>
      <ul>
        {Object.values(DECISIONS).map((d) => (
          <li key={d.label}>
            <span className={`marker tone-${d.tone}`} aria-hidden="true" />
            <div>
              <strong>{d.label}</strong>
              <p>{d.hint}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CreateTicket({ go, onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = { subject: form.subject.trim(), body: form.body.trim(), channel: form.channel };
      if (form.customer_id.trim()) payload.customer_id = form.customer_id.trim();
      if (form.external_id.trim()) payload.external_id = form.external_id.trim();
      const res = await api.createTicket(payload);
      setResult(res);
      onCreated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const reset = () => {
    setForm(EMPTY);
    setResult(null);
    setError("");
  };

  return (
    <>
      <header className="page-head">
        <h1>New ticket</h1>
        <p>Create a ticket and see how the co-pilot triages it.</p>
      </header>

      <div className="split">
        <form className="panel form" onSubmit={submit}>
          <div className="samples" aria-label="Fill with an example">
            <span>Try an example</span>
            {SAMPLES.map((s) => (
              <button
                key={s.label}
                type="button"
                className="chip"
                onClick={() => setForm((f) => ({ ...f, subject: s.subject, body: s.body }))}
              >
                {s.label}
              </button>
            ))}
          </div>

          <label className="field">
            <span>Subject</span>
            <input
              required
              maxLength={300}
              value={form.subject}
              onChange={set("subject")}
              placeholder="What is the customer asking about?"
            />
          </label>

          <label className="field">
            <span>Message</span>
            <textarea
              required
              rows={8}
              maxLength={20000}
              value={form.body}
              onChange={set("body")}
              placeholder="Paste the customer's message"
            />
            <em className="field-hint right">{form.body.length.toLocaleString()} / 20,000</em>
          </label>

          <div className="row2">
            <label className="field">
              <span>Channel</span>
              <select value={form.channel} onChange={set("channel")}>
                <option value="web">Web</option>
                <option value="email">Email</option>
                <option value="chat">Chat</option>
                <option value="api">API</option>
              </select>
            </label>
            <label className="field">
              <span>Customer ID</span>
              <input maxLength={128} value={form.customer_id} onChange={set("customer_id")} placeholder="Optional" />
            </label>
          </div>

          <label className="field">
            <span>External reference</span>
            <input
              maxLength={128}
              value={form.external_id}
              onChange={set("external_id")}
              placeholder="Optional. The ID in your help desk"
            />
          </label>

          {error && (
            <div className="notice bad" role="alert">
              <CircleAlert size={18} aria-hidden="true" />
              <div>{error}</div>
            </div>
          )}

          <div className="actions">
            <button className="btn-primary" type="submit" disabled={busy || !form.subject.trim() || !form.body.trim()}>
              <FilePlus2 size={16} aria-hidden="true" />
              {busy ? "Triaging…" : "Create and triage"}
            </button>
            {(form.subject || form.body) && (
              <button type="button" className="btn-quiet" onClick={reset} disabled={busy}>
                Clear
              </button>
            )}
          </div>
        </form>

        <section className="panel result" aria-live="polite">
          {result ? (
            <>
              <div className="result-head">
                <div>
                  <h2>Triage result</h2>
                  <p className="mono id">Ticket {shortId(result.ticket_id)}</p>
                </div>
                <button type="button" className="btn-secondary" onClick={() => go(`/queue/${result.ticket_id}`)}>
                  Open in queue <ArrowRight size={16} aria-hidden="true" />
                </button>
              </div>
              <TriageSummary result={result} />
            </>
          ) : (
            <Legend />
          )}
        </section>
      </div>
    </>
  );
}
