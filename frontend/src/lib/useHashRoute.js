import { useCallback, useEffect, useState } from "react";

// Tiny hash router: #/new, #/queue, #/queue/<ticketId>, #/insights.
// Hash routes keep the build static: FastAPI never needs a catch-all rule.
function parse() {
  const [page = "new", id = null] = window.location.hash.replace(/^#\/?/, "").split("/");
  return { page: ["new", "queue", "insights"].includes(page) ? page : "new", id: id ? decodeURIComponent(id) : null };
}

export function useHashRoute() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => setRoute(parse());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((path) => {
    window.location.hash = path;
  }, []);
  return [route, go];
}
