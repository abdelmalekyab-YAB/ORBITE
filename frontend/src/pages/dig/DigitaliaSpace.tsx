import { Navigate, Route, Routes, useMatch } from "react-router-dom";
import { useMe } from "../../auth/AuthContext";
import Kanban from "../../components/Kanban";
import Shell from "../../components/Shell";
import { useApi } from "../../lib/hooks";
import type { Project, Ticket } from "../../lib/types";
import Cockpit from "./Cockpit";
import ProjectDetail from "./ProjectDetail";
import Projects from "./Projects";
import Team, { useMembers } from "./Team";
import Triage from "./Triage";
import FinanceHub from "./FinanceHub";
import Access from "./Access";
import Settings from "./Settings";

/** Espace Digitalia. Onglets selon le rôle (règle 3) : dev < pm (+ triage, réglages) < admin (+ finances, accès). */
export default function DigitaliaSpace() {
  const me = useMe();
  const canTriage = me.job === "pm" || me.job === "admin";
  const members = useMembers();
  const queue = useApi<Ticket[]>(canTriage ? "/triage" : null);
  const match = useMatch("/dig/projets/:key");
  const project = useApi<Project>(match ? `/projects/${match.params.key}` : null);
  const context =
    match && project.data ? (
      <div className="ctx">
        <span className="dot" style={{ background: "var(--violet)" }} />
        {project.data.name}
        <span className="muted">· {project.data.client}</span>
      </div>
    ) : (
      <div className="ctx">
        <span className="dot" style={{ background: "var(--neon)" }} />
        Espace Digitalia
      </div>
    );

  return (
    <Shell
      context={context}
      newLabel="Nouveau ticket"
      defaultProject={match?.params.key}
      tabs={[
        { to: "/dig", label: "Cockpit", end: true },
        ...(canTriage
          ? [
              {
                to: "/dig/triage",
                label: "Triage",
                count: queue.data?.filter((t) => t.status === "nouveau").length,
                tone: "grad" as const,
              },
            ]
          : []),
        { to: "/dig/kanban", label: "Kanban" },
        { to: "/dig/projets", label: "Projets" },
        { to: "/dig/equipe", label: "Équipe" },
        ...(me.is_orbit_admin
          ? [
              { to: "/dig/finances", label: "Finances" },
              { to: "/dig/acces", label: "Accès" },
            ]
          : []),
        ...(canTriage ? [{ to: "/dig/reglages", label: "Réglages" }] : []),
      ]}
    >
      <Routes>
        <Route index element={<Cockpit />} />
        <Route
          path="kanban"
          element={
            <>
              <h1 style={{ marginBottom: 4 }}>Kanban</h1>
              <p className="hint" style={{ marginBottom: 16 }}>
                Tous les projets. Glissez une carte pour changer son statut ; la colonne « Chez le client » regroupe devis,
                attente de précision et test.
              </p>
              <Kanban members={members} />
            </>
          }
        />
        {canTriage && <Route path="triage" element={<Triage members={members} />} />}
        <Route path="projets" element={<Projects />} />
        <Route path="projets/:key" element={<ProjectDetail members={members} />} />
        <Route path="equipe" element={<Team />} />
        {me.is_orbit_admin && <Route path="finances" element={<FinanceHub />} />}
        {me.is_orbit_admin && <Route path="acces" element={<Access />} />}
        {canTriage && <Route path="reglages" element={<Settings />} />}
        <Route path="*" element={<Navigate to="/dig" replace />} />
      </Routes>
    </Shell>
  );
}
