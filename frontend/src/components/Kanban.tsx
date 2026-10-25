import { DragEvent, useState } from "react";
import { ApiError, post } from "../lib/api";
import { fmtD, TYPE_LABEL } from "../lib/format";
import { useApi } from "../lib/hooks";
import type { BoardColumn, Project, Ticket, TicketType } from "../lib/types";
import { Avatar, Loading, TypeTag } from "./bits";
import { useUI } from "./UIContext";

const COLUMN_COLOR: Record<string, string> = {
  nouveau: "var(--cyan)",
  analyser: "var(--violet)",
  client: "var(--neon)",
  faire: "var(--ink2)",
  cours: "var(--magenta, #e04bff)",
  testint: "#7c3aed",
  termine: "var(--neon)",
};

interface Filters {
  project: string;
  assignee: string;
  type: string;
  subtasks: boolean;
  q: string;
}

/** Kanban : colonnes issues du workflow ; glisser une carte = transition (refusée si non autorisée). */
export default function Kanban({ project, members }: { project?: string; members: { id: number; name: string }[] }) {
  const { workflow, toast, bump, openTicket } = useUI();
  const [f, setF] = useState<Filters>({ project: "", assignee: "", type: "", subtasks: false, q: "" });
  const projects = useApi<Project[]>(project ? null : "/projects");
  const [over, setOver] = useState<string | null>(null);

  const params = new URLSearchParams();
  const key = project ?? f.project;
  if (key) params.set("project", key);
  if (f.assignee) params.set("assignee", f.assignee);
  if (f.type) params.set("type", f.type);
  if (!f.subtasks) params.set("parent", "none");
  if (f.q) params.set("q", f.q);
  const board = useApi<{ columns: BoardColumn[] }>(`/tickets/board?${params}`);

  async function drop(e: DragEvent, col: BoardColumn) {
    e.preventDefault();
    setOver(null);
    const card: Ticket = JSON.parse(e.dataTransfer.getData("application/json"));
    if (col.statuses.includes(card.status)) return;
    const next = workflow?.statuses.find((s) => s.key === card.status)?.next ?? [];
    const to = col.statuses.find((s) => next.includes(s));
    if (!to) {
      toast(`Transition non autorisée : ${card.status_label} → ${col.label}`);
      return;
    }
    try {
      await post(`/tickets/${card.id}/transition`, { to });
      toast(`${card.ref} → ${workflow?.statuses.find((s) => s.key === to)?.label ?? to}`);
      bump();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Transition impossible");
    }
  }

  const set = (patch: Partial<Filters>) => setF((x) => ({ ...x, ...patch }));
  return (
    <>
      <div className="toolbar">
        {!project && (
          <select
            className="fin-in"
            style={{ width: "auto", textAlign: "left" }}
            aria-label="Projet"
            value={f.project}
            onChange={(e) => set({ project: e.target.value })}
          >
            <option value="">Tous les projets</option>
            {projects.data?.map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
        )}
        <select
          className="fin-in"
          style={{ width: "auto", textAlign: "left" }}
          aria-label="Responsable"
          value={f.assignee}
          onChange={(e) => set({ assignee: e.target.value })}
        >
          <option value="">Tout le monde</option>
          <option value="me">Mes tickets</option>
          <option value="none">Non assigné</option>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <select
          className="fin-in"
          style={{ width: "auto", textAlign: "left" }}
          aria-label="Type"
          value={f.type}
          onChange={(e) => set({ type: e.target.value })}
        >
          <option value="">Tous les types</option>
          {(Object.keys(TYPE_LABEL) as TicketType[]).map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <label className="hint" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={f.subtasks} onChange={(e) => set({ subtasks: e.target.checked })} /> Sous-tâches
        </label>
        <div className="search">
          <input placeholder="Rechercher…" value={f.q} onChange={(e) => set({ q: e.target.value })} />
        </div>
      </div>
      {!board.data ? (
        <Loading />
      ) : (
        <div className="kb">
          {board.data.columns.map((col) => (
            <div
              key={col.key}
              className={`kc ${over === col.key ? "over" : ""}`}
              data-testid={`col-${col.key}`}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(col.key);
              }}
              onDragLeave={() => setOver((o) => (o === col.key ? null : o))}
              onDrop={(e) => drop(e, col)}
            >
              <div className="kh">
                <i style={{ background: COLUMN_COLOR[col.key] ?? "var(--violet)" }} />
                {col.label}
                <span className="cnt">{col.cards.length}</span>
              </div>
              {col.cards.map((t) => (
                <div
                  key={t.id}
                  className="kk"
                  draggable
                  role="button"
                  tabIndex={0}
                  aria-label={`${t.ref} ${t.title}`}
                  onClick={() => openTicket(t.id)}
                  onKeyDown={(e) => e.key === "Enter" && openTicket(t.id)}
                  onDragStart={(e) => {
                    e.dataTransfer.setData("application/json", JSON.stringify(t));
                    e.currentTarget.classList.add("dragging");
                  }}
                  onDragEnd={(e) => e.currentTarget.classList.remove("dragging")}
                >
                  {!project && <div className="p">{t.project_name}</div>}
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <TypeTag type={t.type} />
                    {(t.priority === "high" || t.priority === "critical") && (
                      <span className="tag" style={{ color: "var(--rose)" }}>
                        {t.priority === "critical" ? "Critique" : "Haute"}
                      </span>
                    )}
                    {t.is_internal && <span className="tag int">🔒</span>}
                  </div>
                  <div className="t">{t.title}</div>
                  <div className="m">
                    <span>{t.ref}</span>
                    {t.due_on && <span className={t.is_late ? "late" : ""}>📅 {fmtD(t.due_on)}</span>}
                    {col.key === "client" && (
                      <span className="ball you" style={{ padding: "1px 7px", fontSize: 10.5 }}>
                        {t.status_label}
                      </span>
                    )}
                    <Avatar user={t.assignee} small />
                  </div>
                </div>
              ))}
              {!col.cards.length && <div className="kdrop">Déposer ici</div>}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
