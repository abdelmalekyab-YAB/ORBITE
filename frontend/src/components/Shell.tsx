import { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth, useMe } from "../auth/AuthContext";
import { Avatar } from "./bits";
import NewRequestModal from "./NewRequestModal";
import NotificationBell from "./NotificationBell";
import TicketDrawer from "./TicketDrawer";
import { useUI } from "./UIContext";

export interface Tab {
  to: string;
  label: string;
  count?: number;
  tone?: "neon" | "grad";
  end?: boolean;
}

const OrbitMark = () => (
  <svg viewBox="0 0 32 32" aria-hidden="true">
    <defs>
      <linearGradient id="og" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#e04bff" />
        <stop offset="1" stopColor="#7c3aed" />
      </linearGradient>
    </defs>
    <circle cx="16" cy="16" r="12" fill="none" stroke="url(#og)" strokeWidth="3" />
    <circle cx="26" cy="9" r="3" fill="#3dffb7" />
  </svg>
);

/** Topbar + contenu + fiche ticket + modale de création (shell commun aux deux espaces). */
export default function Shell({
  tabs,
  context,
  children,
  newLabel,
  defaultProject,
}: {
  tabs: Tab[];
  context: ReactNode;
  children: ReactNode;
  newLabel?: string;
  defaultProject?: string;
}) {
  const me = useMe();
  const { logout } = useAuth();
  const { setNewRequest } = useUI();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  return (
    <>
      <header className="top">
        <div className="logo">
          <OrbitMark />
          Orbit
          <i />
        </div>
        <img
          src={`${import.meta.env.BASE_URL}logo-digitalia.png`}
          alt="Digitalia"
          title="Développé par Digitalia"
          style={{ height: 26, opacity: 0.85, marginLeft: -6 }}
        />
        {context}
        {tabs.length > 0 && (
          <nav className="tabs">
            {tabs.map((t) => {
              const active = t.end ? pathname === t.to : pathname === t.to || pathname.startsWith(`${t.to}/`);
              return (
                <button
                  key={t.to}
                  className={active ? "on" : ""}
                  aria-current={active ? "page" : undefined}
                  onClick={() => navigate(t.to)}
                >
                  {t.label}
                  {t.count ? <span className={`n ${t.tone ?? ""}`}>{t.count}</span> : null}
                </button>
              );
            })}
          </nav>
        )}
        {newLabel && (
          <button className="btn white" onClick={() => setNewRequest(true)}>
            ＋ {newLabel}
          </button>
        )}
        <NotificationBell />
        <button
          className="btn ghost"
          title="Déconnexion"
          aria-label="Déconnexion"
          style={tabs.length ? undefined : { marginLeft: "auto" }}
          onClick={() => {
            logout();
            navigate("/login");
          }}
        >
          <Avatar user={{ id: me.id, name: me.name, initials: me.initials, job: me.job }} /> ⏻
        </button>
      </header>
      <main className="wrap">{children}</main>
      <TicketDrawer />
      <NewRequestModal defaultProject={defaultProject} />
    </>
  );
}
