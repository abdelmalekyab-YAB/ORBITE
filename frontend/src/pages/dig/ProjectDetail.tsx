import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMe } from "../../auth/AuthContext";
import ProjectFinanceTab from "../../components/ProjectFinanceTab";
import { Avatar, Empty, HealthBadge, Loading, TypeTag } from "../../components/bits";
import ExportButton from "../../components/ExportButton";
import Kanban from "../../components/Kanban";
import ReqRow from "../../components/ReqRow";
import Roadmap from "../../components/Roadmap";
import { useUI } from "../../components/UIContext";
import { useApi } from "../../lib/hooks";
import type { Page, Project, Ticket } from "../../lib/types";

type Tab = "req" | "kanban" | "road" | "int" | "fin";
type Segment = "all" | "dig" | "you" | "done";

export default function ProjectDetail({ members }: { members: { id: number; name: string }[] }) {
  const { key = "" } = useParams();
  const project = useApi<Project>(`/projects/${key}`);
  const tickets = useApi<Page<Ticket>>(`/tickets?project=${key}`);
  const me = useMe();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(params.get("tab") === "fin" && me.is_orbit_admin ? "fin" : "req");
  const [seg, setSeg] = useState<Segment>("all");
  const [q, setQ] = useState("");
  const { openTicket } = useUI();

  if (project.error)
    return (
      <div className="card">
        <Empty title="Projet introuvable" />
      </div>
    );
  if (!project.data || !tickets.data) return <Loading />;
  const p = project.data;
  const all = tickets.data.results;
  const visible = all.filter((t) => !t.is_internal);
  const internal = all.filter((t) => t.is_internal);
  const open = visible.filter((t) => !t.is_closed);
  const bySeg: Record<Segment, Ticket[]> = {
    all: open,
    dig: open.filter((t) => t.ball === "digitalia"),
    you: open.filter((t) => t.ball === "client"),
    done: visible.filter((t) => t.is_closed),
  };
  const needle = q.trim().toLowerCase();
  const list = bySeg[seg].filter(
    (t) => !needle || t.title.toLowerCase().includes(needle) || t.ref.toLowerCase().includes(needle),
  );

  return (
    <>
      <Link to="/dig/projets" className="btn ghost sm">
        ← Projets
      </Link>
      <div style={{ display: "flex", alignItems: "center", gap: 14, margin: "8px 0 6px", flexWrap: "wrap" }}>
        <h1>{p.name}</h1>
        <HealthBadge health={p.health} />
      </div>
      <p className="hint" style={{ marginBottom: 16 }}>
        {p.client} · responsable {p.lead?.name ?? "—"} · {p.reason}
      </p>
      <div className="chips" style={{ marginBottom: 18 }}>
        {(
          [
            ["req", "Demandes"],
            ["kanban", "Kanban"],
            ["road", "Versions"],
            ["int", `Interne (${internal.length})`],
          ] as [Tab, string][]
        )
          .concat(me.is_orbit_admin ? [["fin", "Finances"]] : [])
          .map(([k, l]) => (
            <button key={k} className={`chip ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>
              {l}
            </button>
          ))}
      </div>

      {tab === "req" && (
        <>
          <div className="toolbar">
            <div className="chips">
              {(
                [
                  ["all", "Ouvertes"],
                  ["dig", "Chez Digitalia"],
                  ["you", "Chez le client"],
                  ["done", "Livrées"],
                ] as [Segment, string][]
              ).map(([k, l]) => (
                <button key={k} className={`chip ${seg === k ? "on" : ""}`} onClick={() => setSeg(k)}>
                  {l} <span className="muted">{bySeg[k].length}</span>
                </button>
              ))}
            </div>
            <div className="search">
              <input placeholder="Rechercher…" aria-label="Rechercher" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <ExportButton path={`/tickets/export.csv?project=${p.key}`} filename={`orbit-${p.key}.csv`} />
          </div>
          {list.length ? (
            list.map((t) => <ReqRow key={t.id} ticket={t} forDigitalia />)
          ) : (
            <div className="card">
              <Empty title="Aucune demande" />
            </div>
          )}
        </>
      )}

      {tab === "kanban" && <Kanban project={p.key} members={members} />}

      {tab === "road" && <Roadmap project={p.key} tickets={all} />}

      {tab === "fin" && me.is_orbit_admin && <ProjectFinanceTab projectKey={p.key} />}

      {tab === "int" && (
        <>
          <p className="hint" style={{ marginBottom: 12 }}>
            Tâches techniques et sous-tâches, invisibles pour le client.
          </p>
          {internal.length ? (
            internal.map((t) => (
              <div className="req" key={t.id} onClick={() => openTicket(t.id)}>
                <div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <TypeTag type={t.type} />
                    {t.parent && <span className="hint">↳ {t.parent.title}</span>}
                  </div>
                  <div className="t">{t.title}</div>
                  <div className="meta">
                    <span className="ref">{t.ref}</span>
                    <span className="step-now">{t.status_label}</span>
                  </div>
                </div>
                <div className="right">
                  <Avatar user={t.assignee} small />
                </div>
              </div>
            ))
          ) : (
            <div className="card">
              <Empty title="Aucune tâche interne" />
            </div>
          )}
        </>
      )}
    </>
  );
}
