import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api/client";

const links = [
  { to: "/", label: "Launch & Runs", end: true },
  { to: "/graphs", label: "Graph Explorer" },
  { to: "/architecture", label: "Agent Architecture" },
  { to: "/presentation", label: "Presentation" },
  { to: "/demo", label: "Recorded Demo" },
  { to: "/evidence", label: "Evidence Dashboard" },
];

export default function NavBar() {
  const [phase, setPhase] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => {
        if (!cancelled) {
          setPhase(`${h.llm_provider} · ${h.phase}`);
          setOnline(true);
        }
      })
      .catch(() => {
        if (!cancelled) setOnline(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="navbar">
      <div className="navbar__brand">
        <span className="navbar__mark" aria-hidden="true">CA</span>
        <span className="navbar__brand-copy">
          <span className="navbar__logo">CausalAtlas</span>
          <span className="navbar__tagline">evidence → graph → experiment</span>
        </span>
        <span className="navbar__runtime" title={online === false ? "The API is not reachable" : phase ?? "Checking API status"}>
          <span className={`status-dot ${online ? "status-dot--ok" : online === false ? "status-dot--down" : ""}`} />
          <span className="navbar__phase">{online === false ? "offline" : phase ?? "connecting…"}</span>
        </span>
      </div>
      <nav className="navbar__links" aria-label="Primary navigation">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.end}
            className={({ isActive }) => `navbar__link${isActive ? " navbar__link--active" : ""}`}
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
