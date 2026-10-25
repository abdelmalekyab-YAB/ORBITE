import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useMe } from "../../auth/AuthContext";
import { Empty } from "../../components/bits";
import Shell from "../../components/Shell";
import { useApi } from "../../lib/hooks";
import type { Page, Ticket } from "../../lib/types";
import ClientHome from "./ClientHome";
import ClientRequests from "./ClientRequests";
import ClientRoadmap from "./ClientRoadmap";

export type Scope = "all" | string;

export default function ClientSpace() {
  const me = useMe();
  const projects = me.projects;
  const [scope, setScope] = useState<Scope>(projects.length > 1 ? "all" : (projects[0]?.key ?? "all"));
  const query = scope === "all" ? "" : `?project=${scope}`;
  const { data } = useApi<Page<Ticket>>(projects.length ? `/tickets${query}` : null);
  const tickets = data?.results ?? null;
  const yours = tickets?.filter((t) => !t.is_closed && t.ball === "client").length ?? 0;

  // Règle 5 : pas de projet ouvert → écran vide, pas une erreur.
  if (!projects.length) {
    return (
      <Shell
        tabs={[]}
        context={
          <div className="ctx">
            <span className="dot" style={{ background: "var(--mute)" }} />
            {me.organization}
          </div>
        }
      >
        <div className="card" style={{ maxWidth: 560, margin: "40px auto" }}>
          <Empty title="Aucun projet ouvert pour l'instant">
            Votre compte est actif mais aucun projet ne vous est encore rattaché. Digitalia vous ouvrira l'accès dès que votre
            projet sera en production.
          </Empty>
        </div>
      </Shell>
    );
  }

  const context =
    projects.length > 1 ? (
      <>
        <div className="ctx" style={{ padding: 4 }}>
          <select
            aria-label="Projet"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            style={{ border: 0, background: "none", fontWeight: 700, color: "var(--ink)", padding: "4px 8px" }}
          >
            <option value="all">Tous mes projets ({projects.length})</option>
            {projects.map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <span className="hint">{projects[0].client}</span>
      </>
    ) : (
      <div className="ctx">
        <span className="dot" style={{ background: "var(--violet)" }} />
        {projects[0].name}
        <span className="muted">· {projects[0].client}</span>
      </div>
    );

  return (
    <Shell
      context={context}
      newLabel="Nouvelle demande"
      defaultProject={scope === "all" ? undefined : scope}
      tabs={[
        { to: "/app", label: "Accueil", count: yours, tone: "neon", end: true },
        { to: "/app/demandes", label: "Mes demandes" },
        { to: "/app/feuille-de-route", label: "Feuille de route" },
      ]}
    >
      <Routes>
        <Route index element={<ClientHome tickets={tickets} scope={scope} onScope={setScope} />} />
        <Route path="demandes" element={<ClientRequests tickets={tickets} showProject={scope === "all"} />} />
        <Route path="feuille-de-route" element={<ClientRoadmap tickets={tickets} scope={scope} />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </Shell>
  );
}
