// Thin client for the FastAPI backend. All paths are relative, so the same build works behind
// the Vite dev proxy, the Docker image (FastAPI serves the UI) and the ALB on AWS.
// Set VITE_API_BASE only if the API lives on a different origin.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI returns {detail: "text"} for HTTPException and {detail: [{loc, msg}]} for 422s.
function describe(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = (d.loc || []).filter((p) => p !== "body").join(".");
        const msg = String(d.msg).replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

async function request(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the API. Check that the backend is running on port 8000.", 0);
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON error page */
  }
  if (!res.ok) throw new ApiError(describe(data?.detail, res.status), res.status);
  return data;
}

export const api = {
  health: () => request("/healthz"),
  policy: () => request("/v1/policy"),

  createTicket: (payload) => request("/v1/tickets", { method: "POST", body: payload }),
  getTicket: (id) => request(`/v1/tickets/${encodeURIComponent(id)}`),

  // The three queue endpoints. Paths match app/api/tickets.py exactly (they are case-sensitive).
  listAll: () => request("/v1/tickets"),
  listDrafted: () => request("/v1/tickets/AI_drafted_tickets"),
  listEscalated: () => request("/v1/tickets/Escalated_tickets"),

  submitFeedback: (id, body) =>
    request(`/v1/tickets/${encodeURIComponent(id)}/feedback`, { method: "POST", body }),
  feedbackStats: (days = 7) => request(`/v1/feedback/stats?days=${days}`),
};
