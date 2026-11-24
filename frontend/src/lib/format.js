export const DECISIONS = {
  draft_ready: { label: "Draft ready", tone: "draft", hint: "Confident and grounded in the knowledge base. A reply is drafted for an agent to review." },
  human_triage: { label: "Human triage", tone: "triage", hint: "Low confidence or no matching knowledge-base answer. Goes to the normal queue without a draft." },
  escalate: { label: "Escalate", tone: "escalate", hint: "A never-auto-respond category. A person handles it and no draft is written." },
};

export const decisionOf = (d) => DECISIONS[d] ?? { label: d ?? "Not triaged", tone: "none", hint: "" };

export const CATEGORY_LABELS = {
  password_reset: "Password reset",
  shipping_status: "Shipping status",
  product_how_to: "Product how-to",
  account_settings: "Account settings",
  general_inquiry: "General inquiry",
  legal_threat: "Legal threat",
  security_incident: "Security incident",
  payment_dispute: "Payment dispute",
  privacy_request: "Privacy request",
  safety_or_harassment: "Safety or harassment",
  other: "Other",
};

export const categoryLabel = (c) =>
  CATEGORY_LABELS[c] ?? (c ? c.replace(/_/g, " ").replace(/^./, (m) => m.toUpperCase()) : "Unknown");

export const pct = (n, digits = 0) => (n == null ? "–" : `${(n * 100).toFixed(digits)}%`);

export function timeAgo(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.round(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export const fullDate = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

export const shortId = (id) => (id ? String(id).slice(0, 8) : "");

// Example tickets so the three routing outcomes can be demoed in one click.
export const SAMPLES = [
  { label: "Password reset", subject: "Locked out of my account", body: "I forgot my password and the reset email never arrives. How do I reset it so I can log in again?" },
  { label: "Shipping status", subject: "Where is my order?", body: "My package was supposed to arrive last week. Can you check the tracking and delivery status for my order?" },
  { label: "Legal threat", subject: "Final warning", body: "If this isn't fixed today my lawyer will start legal action against your company." },
  { label: "Unrelated", subject: "Sponsorship", body: "Do you sponsor local football clubs or community events?" },
];
