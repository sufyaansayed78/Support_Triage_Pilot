import { useState } from "react";
import { CircleAlert, CircleCheck, Pencil, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../lib/api";
import { pct } from "../lib/format";

const ACTIONS = [
  { value: "accept", label: "Accept", icon: ThumbsUp, hint: "Send the draft as written." },
  { value: "edit", label: "Edit", icon: Pencil, hint: "Rewrite the draft. The size of your change is recorded." },
  { value: "reject", label: "Reject", icon: ThumbsDown, hint: "The draft is wrong or unusable." },
];

const AGENT_KEY = "triage.agentId";
const readAgent = () => {
  try {
    return localStorage.getItem(AGENT_KEY) || "";
  } catch {
    return "";
  }
};

export default function FeedbackForm({ ticketId, draft, onSent }) {
  const [action, setAction] = useState("accept");
  const [edited, setEdited] = useState(draft || "");
  const [agent, setAgent] = useState(readAgent);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(null);

  const editInvalid = action === "edit" && !edited.trim();
  const editUnchanged = action === "edit" && edited.trim() === (draft || "").trim();
  const current = ACTIONS.find((a) => a.value === action);

  async function submit(e) {
    e.preventDefault();
    if (editInvalid) return;
    setBusy(true);
    setError("");
    try {
      const body = { action };
      if (action === "edit") body.edited_text = edited;
      if (agent.trim()) body.agent_id = agent.trim();
      if (reason.trim()) body.reason = reason.trim();
      const record = await api.submitFeedback(ticketId, body);
      try {
        localStorage.setItem(AGENT_KEY, agent.trim());
      } catch {
        /* private mode: ignore */
      }
      setSent(record);
      onSent?.(record);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    const verb = { accept: "accepted", edit: "edited", reject: "rejected" }[sent.action];
    return (
      <div className="notice ok" role="status">
        <CircleCheck size={18} aria-hidden="true" />
        <div>
          <strong>Feedback sent</strong>
          <p>
            You {verb} this draft.
            {sent.edit_ratio != null && ` About ${pct(sent.edit_ratio)} of the draft was rewritten.`} The ticket has
            left the pending queues.
          </p>
        </div>
      </div>
    );
  }

  return (
    <form className="feedback" onSubmit={submit}>
      <div className="segmented" role="radiogroup" aria-label="Feedback on the draft">
        {ACTIONS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={action === value}
            className={`seg seg-${value}${action === value ? " on" : ""}`}
            onClick={() => setAction(value)}
          >
            <Icon size={16} aria-hidden="true" /> {label}
          </button>
        ))}
      </div>
      <p className="hint">{current.hint}</p>

      {action === "edit" && (
        <label className="field">
          <span>Your reply</span>
          <textarea rows={8} value={edited} onChange={(e) => setEdited(e.target.value)} maxLength={20000} />
          {editInvalid && <em className="field-error">Write the reply you would send.</em>}
          {!editInvalid && editUnchanged && (
            <em className="field-hint">Same as the draft. Choose Accept if you changed nothing.</em>
          )}
        </label>
      )}

      <div className="row2">
        <label className="field">
          <span>Agent ID</span>
          <input value={agent} onChange={(e) => setAgent(e.target.value)} maxLength={128} placeholder="Optional" />
        </label>
        <label className="field">
          <span>Reason</span>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={1000}
            placeholder={action === "reject" ? "What was wrong?" : "Optional"}
          />
        </label>
      </div>

      {error && (
        <div className="notice bad" role="alert">
          <CircleAlert size={18} aria-hidden="true" />
          <div>{error}</div>
        </div>
      )}

      <button className="btn-primary" type="submit" disabled={busy || editInvalid}>
        <Send size={16} aria-hidden="true" />
        {busy ? "Sending…" : "Send feedback"}
      </button>
    </form>
  );
}
