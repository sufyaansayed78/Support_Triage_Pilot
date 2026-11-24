import { decisionOf } from "../lib/format";

export function DecisionBadge({ decision }) {
  const d = decisionOf(decision);
  return (
    <span className={`badge tone-${d.tone}`}>
      <span className="dot" aria-hidden="true" />
      {d.label}
    </span>
  );
}

// What an agent should do next with this ticket.
export function statusOf(record) {
  const { ticket, result } = record;
  if (!result) return { label: "Not triaged", tone: "none" };
  if (ticket.feedback_status === "Submitted") return { label: "Reviewed", tone: "done" };
  if (result.decision === "draft_ready") return { label: "Awaiting review", tone: "draft" };
  return { label: "Needs a person", tone: result.decision === "escalate" ? "escalate" : "triage" };
}

export function StatusPill({ record }) {
  const s = statusOf(record);
  return <span className={`pill tone-${s.tone}`}>{s.label}</span>;
}
