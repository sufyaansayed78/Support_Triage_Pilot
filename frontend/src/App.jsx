import { useCallback, useEffect, useState } from "react";
import { Activity, ChartNoAxesColumn, FilePlus2, Inbox } from "lucide-react";
import { api } from "./lib/api";
import { useHashRoute } from "./lib/useHashRoute";
import CreateTicket from "./pages/CreateTicket";
import Queue from "./pages/Queue";
import Insights from "./pages/Insights";

const NAV = [
  { page: "new", to: "/new", label: "New ticket", icon: FilePlus2 },
  { page: "queue", to: "/queue", label: "Queue", icon: Inbox },
  { page: "insights", to: "/insights", label: "Insights", icon: ChartNoAxesColumn },
];

function ApiStatus() {
  const [up, setUp] = useState(null);
  useEffect(() => {
    let live = true;
    const ping = () =>
      api
        .health()
        .then(() => live && setUp(true))
        .catch(() => live && setUp(false));
    ping();
    const id = setInterval(ping, 30000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, []);
  const text = up == null ? "Checking API…" : up ? "API online" : "API unreachable";
  return (
    <p className={`api-status ${up == null ? "" : up ? "up" : "down"}`} role="status">
      <Activity size={14} aria-hidden="true" /> {text}
    </p>
  );
}

export default function App() {
  const [{ page, id }, go] = useHashRoute();
  // Bumped whenever tickets change so the queue and insights refetch.
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = useCallback(() => setRefreshKey((k) => k + 1), []);

  return (
    <div className="app">
      <nav className="rail" aria-label="Main">
        <a className="brand" href="#/new">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="#fff" fillOpacity=".12" />
            <path d="M7 20h5l3-9 4 13 3-7h3" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Triage Co-pilot</span>
        </a>
        <ul>
          {NAV.map(({ page: p, to, label, icon: Icon }) => (
            <li key={p}>
              <a href={`#${to}`} className={page === p ? "on" : ""} aria-current={page === p ? "page" : undefined}>
                <Icon size={18} aria-hidden="true" />
                {label}
              </a>
            </li>
          ))}
        </ul>
        <ApiStatus />
      </nav>

      <main>
        {page === "new" && <CreateTicket go={go} onCreated={bump} />}
        {page === "queue" && <Queue selectedId={id} go={go} refreshKey={refreshKey} />}
        {page === "insights" && <Insights go={go} refreshKey={refreshKey} />}
      </main>
    </div>
  );
}
