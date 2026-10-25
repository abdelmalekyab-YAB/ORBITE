import { useEffect, useMemo, useState } from "react";
import { useMe } from "../auth/AuthContext";
import { ApiError, api, post } from "../lib/api";
import { fmtD } from "../lib/format";
import { progressOf } from "../lib/health";
import { useApi } from "../lib/hooks";
import type { Milestone, Ticket } from "../lib/types";
import { Empty, Loading } from "./bits";
import ReqRow from "./ReqRow";
import { useUI } from "./UIContext";

/** Versions d'un projet et leur contenu (composant `versions` de la maquette). */
export default function Roadmap({ project, tickets }: { project: string; tickets: Ticket[] }) {
  const me = useMe();
  const { toast, bump } = useUI();
  const milestones = useApi<Milestone[]>(`/projects/${project}/milestones`);
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState<Milestone | "new" | null>(null);
  const today = new Date().toISOString().slice(0, 10);

  const list = useMemo(() => milestones.data ?? [], [milestones.data]);
  useEffect(() => {
    if (selected && list.some((m) => m.id === selected)) return;
    const current =
      list.find((m) => (m.starts_on ?? "") <= today && today <= (m.ends_on ?? "9999")) ??
      list.find((m) => (m.starts_on ?? "") > today) ??
      list[list.length - 1];
    setSelected(current?.id ?? null);
  }, [list, selected, today]);

  if (!milestones.data) return <Loading />;
  const visible = tickets.filter((t) => t.project === project && !t.is_internal);
  const version = list.find((m) => m.id === selected);
  const content = visible.filter((t) => t.milestone?.id === selected);
  const unplanned = visible.filter((t) => !t.milestone && !t.is_closed);

  async function save(values: Partial<Milestone>) {
    try {
      if (editing === "new") await post(`/projects/${project}/milestones`, values);
      else if (editing)
        await api(`/projects/${project}/milestones/${editing.id}`, { method: "PATCH", body: JSON.stringify(values) });
      setEditing(null);
      milestones.reload();
      bump();
      toast("Version enregistrée");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Enregistrement impossible");
    }
  }
  async function remove(m: Milestone) {
    if (!window.confirm(`Supprimer ${m.name} ? Ses demandes repasseront « pas encore planifiées ».`)) return;
    await api(`/projects/${project}/milestones/${m.id}`, { method: "DELETE" });
    setEditing(null);
    milestones.reload();
    bump();
  }

  return (
    <>
      <div className="versions">
        {list.map((m) => {
          const ml = visible.filter((t) => t.milestone?.id === m.id);
          const p = progressOf(ml);
          const [cls, label] =
            p === 100 && ml.length ? ["you", "Livrée"] : (m.starts_on ?? "") <= today ? ["dig", "En cours"] : ["done", "À venir"];
          return (
            <div
              key={m.id}
              className={`ver ${selected === m.id ? "on" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => setSelected(m.id)}
              onKeyDown={(e) => e.key === "Enter" && setSelected(m.id)}
            >
              <span className={`st ball ${cls}`}>{label}</span>
              <h2>{m.name}</h2>
              <div className="d">Objectif {fmtD(m.ends_on)}</div>
              <div className={`prog ${p === 100 ? "neon" : ""}`}>
                <i style={{ width: `${p}%` }} />
              </div>
              <div className="n">
                <span>
                  {ml.filter((t) => t.client_label === "Livrée").length}/{ml.length} livrées
                </span>
                <span>{p}%</span>
              </div>
              {me.is_digitalia && (
                <button
                  className="btn ghost sm"
                  style={{ marginTop: 8 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditing(m);
                  }}
                >
                  Modifier
                </button>
              )}
            </div>
          );
        })}
        {me.is_digitalia && (
          <button className="ver" style={{ textAlign: "left", color: "var(--ink2)" }} onClick={() => setEditing("new")}>
            <h2>＋ Nouvelle version</h2>
            <div className="d">Nom, début, objectif</div>
          </button>
        )}
      </div>
      {editing && (
        <MilestoneForm
          value={editing === "new" ? undefined : editing}
          onCancel={() => setEditing(null)}
          onSave={save}
          onDelete={editing !== "new" ? () => remove(editing) : undefined}
        />
      )}
      {version ? (
        <div className="card">
          <h2>
            {version.name}{" "}
            <span className="cnt">
              {fmtD(version.starts_on)} → {fmtD(version.ends_on)}
            </span>
          </h2>
          {content.length ? (
            content.map((t) => <ReqRow key={t.id} ticket={t} forDigitalia={me.is_digitalia} />)
          ) : (
            <Empty title="Rien de planifié pour l'instant">Le contenu sera ajouté par Digitalia.</Empty>
          )}
        </div>
      ) : (
        <div className="card">
          <Empty title="Aucune version prévue" />
        </div>
      )}
      {unplanned.length > 0 && (
        <div className="card" style={{ marginTop: 18 }}>
          <h2>
            Pas encore planifié <span className="cnt">{unplanned.length}</span>
          </h2>
          {unplanned.map((t) => (
            <ReqRow key={t.id} ticket={t} forDigitalia={me.is_digitalia} />
          ))}
        </div>
      )}
    </>
  );
}

function MilestoneForm({
  value,
  onSave,
  onCancel,
  onDelete,
}: {
  value?: Milestone;
  onSave: (v: Partial<Milestone>) => void;
  onCancel: () => void;
  onDelete?: () => void;
}) {
  const [v, setV] = useState({ name: value?.name ?? "", starts_on: value?.starts_on ?? "", ends_on: value?.ends_on ?? "" });
  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <h2>{value ? `Modifier ${value.name}` : "Nouvelle version"}</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10, alignItems: "end" }}>
        <label className="field">
          Nom
          <input value={v.name} placeholder="Version 3.1" onChange={(e) => setV({ ...v, name: e.target.value })} />
        </label>
        <label className="field">
          Début
          <input type="date" value={v.starts_on} onChange={(e) => setV({ ...v, starts_on: e.target.value })} />
        </label>
        <label className="field">
          Objectif
          <input type="date" value={v.ends_on} onChange={(e) => setV({ ...v, ends_on: e.target.value })} />
        </label>
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 12 }}>
        {onDelete && (
          <button className="btn rose sm" style={{ marginRight: "auto" }} onClick={onDelete}>
            Supprimer
          </button>
        )}
        <button className="btn ghost sm" onClick={onCancel}>
          Annuler
        </button>
        <button
          className="btn grad sm"
          disabled={!v.name.trim()}
          onClick={() =>
            onSave({
              name: v.name.trim(),
              starts_on: v.starts_on || null,
              ends_on: v.ends_on || null,
            })
          }
        >
          Enregistrer
        </button>
      </div>
    </div>
  );
}
