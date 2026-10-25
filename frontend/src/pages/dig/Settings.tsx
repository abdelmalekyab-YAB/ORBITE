import { useEffect, useState } from "react";
import { useMe } from "../../auth/AuthContext";
import { Loading } from "../../components/bits";
import { useUI } from "../../components/UIContext";
import { ApiError, api, post } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import type { Ball, Workflow, WorkflowStatus } from "../../lib/types";

const SYSTEM = ["nouveau", "termine", "refuse", "annule"];
type Row = Pick<WorkflowStatus, "key" | "label" | "client_label" | "ball" | "is_closed" | "is_terminal_ok" | "color" | "next">;

const CLIENT_NOTIFS: [string, string][] = [
  ["client_qualified", "La demande est reçue et qualifiée"],
  ["client_planned", "Elle est planifiée dans une version (avec la date)"],
  ["client_info_requested", "Une précision lui est demandée"],
  ["client_ready_to_test", "Elle est prête à tester"],
  ["client_quote_sent", "Une proposition commerciale l'attend"],
  ["client_delivered", "Elle est livrée"],
  ["client_reminder", "Rappel quand la balle est chez lui depuis plusieurs jours"],
];
const TEAM_NOTIFS: [string, string][] = [
  ["dig_new_request", "Nouvelle demande (responsable du projet + chefs de projet)"],
  ["dig_client_replied", "Le client a répondu"],
  ["dig_client_tested", "Le client a testé"],
  ["dig_quote_decided", "Le client a décidé sur un devis"],
  ["dig_daily_digest", "Récapitulatif quotidien des nouvelles demandes"],
];

export default function Settings() {
  const me = useMe();
  return (
    <>
      <h1 style={{ marginBottom: 4 }}>Réglages</h1>
      <p className="hint" style={{ marginBottom: 18 }}>
        Workflow et notifications.
        {me.is_orbit_admin ? " Les utilisateurs, clients et projets sont dans l'onglet Accès." : ""}
      </p>
      <div className="settings">
        <WorkflowEditor />
        <Notifications />
      </div>
    </>
  );
}

function WorkflowEditor() {
  const { data, reload } = useApi<Workflow>("/workflow");
  const { toast, bump } = useUI();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (data) {
      setRows(
        data.statuses.map(({ key, label, client_label, ball, is_closed, is_terminal_ok, color, next }) => ({
          key,
          label,
          client_label,
          ball,
          is_closed,
          is_terminal_ok,
          color,
          next: [...next],
        })),
      );
      setDirty(false);
    }
  }, [data]);
  if (!rows)
    return (
      <div className="card">
        <Loading />
      </div>
    );

  const update = (next: Row[]) => {
    setRows(next);
    setDirty(true);
  };
  const set = (i: number, patch: Partial<Row>) => update(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const move = (i: number, dir: -1 | 1) => {
    const next = [...rows];
    [next[i], next[i + dir]] = [next[i + dir], next[i]];
    update(next);
  };
  const toggle = (i: number, key: string) =>
    set(i, { next: rows[i].next.includes(key) ? rows[i].next.filter((k) => k !== key) : [...rows[i].next, key] });
  const remove = (i: number) =>
    update(rows.filter((_, j) => j !== i).map((r) => ({ ...r, next: r.next.filter((k) => k !== rows[i].key) })));
  const add = () => {
    const n = rows.filter((r) => r.key.startsWith("statut")).length + 1;
    const at = rows.findIndex((r) => r.is_closed);
    const next = [...rows];
    next.splice(at < 0 ? rows.length : at, 0, {
      key: `statut${n}`,
      label: `Nouveau statut ${n}`,
      client_label: "En développement",
      ball: "digitalia",
      is_closed: false,
      is_terminal_ok: false,
      color: "#a855f7",
      next: [],
    });
    update(next);
  };

  async function save() {
    try {
      await api("/workflow", { method: "PUT", body: JSON.stringify({ statuses: rows }) });
      toast("Workflow enregistré — appliqué au kanban, aux fiches et à l'espace client");
      reload();
      bump();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Enregistrement impossible");
    }
  }
  async function reset() {
    if (!window.confirm("Revenir au workflow par défaut ?")) return;
    try {
      await post("/workflow/reset", {});
      toast("Workflow par défaut rétabli");
      reload();
      bump();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Impossible");
    }
  }

  const steps: string[] = [];
  rows.forEach((r) => {
    if (!r.is_closed && !steps.includes(r.client_label)) steps.push(r.client_label);
  });
  steps.push(rows.find((r) => r.is_terminal_ok)?.client_label ?? "Livrée");

  return (
    <>
      <div className="card">
        <h2>
          Workflow <span className="cnt">configurable</span>
        </h2>
        <p className="hint" style={{ marginBottom: 12 }}>
          Chaque statut interne : le nom que voit le client, chez qui est la balle, et vers quels statuts on peut aller. Les
          modifications s'appliquent au kanban, aux fiches et à l'espace client.
        </p>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Statut interne</th>
                <th>Étape vue par le client</th>
                <th>La balle est chez</th>
                <th>Transitions autorisées</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((w, i) => (
                <tr key={w.key}>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button
                      className="btn ghost sm"
                      aria-label={`Monter ${w.label}`}
                      disabled={i === 0}
                      onClick={() => move(i, -1)}
                    >
                      ▲
                    </button>
                    <button
                      className="btn ghost sm"
                      aria-label={`Descendre ${w.label}`}
                      disabled={i === rows.length - 1}
                      onClick={() => move(i, 1)}
                    >
                      ▼
                    </button>
                  </td>
                  <td>
                    <input
                      className="fin-in"
                      style={{ width: 150, textAlign: "left" }}
                      aria-label={`Nom du statut ${w.key}`}
                      value={w.label}
                      onChange={(e) => set(i, { label: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="fin-in"
                      style={{ width: 170, textAlign: "left" }}
                      aria-label={`Étape client ${w.key}`}
                      value={w.client_label}
                      disabled={w.is_closed}
                      onChange={(e) => set(i, { client_label: e.target.value })}
                    />
                  </td>
                  <td>
                    {w.is_closed ? (
                      <span className="hint">— clôturé</span>
                    ) : (
                      <select
                        className="fin-in"
                        style={{ width: "auto", textAlign: "left" }}
                        aria-label={`Balle ${w.key}`}
                        value={w.ball}
                        onChange={(e) => set(i, { ball: e.target.value as Ball })}
                      >
                        <option value="digitalia">Digitalia</option>
                        <option value="client">Client</option>
                      </select>
                    )}
                  </td>
                  <td style={{ minWidth: 420 }}>
                    <div className="chips" style={{ gap: 4 }}>
                      {rows
                        .filter((x) => x.key !== w.key)
                        .map((x) => (
                          <button
                            key={x.key}
                            className={`chip ${w.next.includes(x.key) ? "on" : ""}`}
                            style={{ padding: "3px 9px", fontSize: 11.5 }}
                            aria-pressed={w.next.includes(x.key)}
                            onClick={() => toggle(i, x.key)}
                          >
                            {x.label}
                          </button>
                        ))}
                    </div>
                  </td>
                  <td>
                    {!SYSTEM.includes(w.key) && (
                      <button
                        className="btn ghost sm"
                        title="Supprimer"
                        aria-label={`Supprimer ${w.label}`}
                        onClick={() => remove(i)}
                      >
                        ✕
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn sm" onClick={add}>
            ＋ Ajouter un statut
          </button>
          <button className="btn ghost sm" onClick={reset}>
            Revenir au workflow par défaut
          </button>
          <button className="btn grad sm" style={{ marginLeft: "auto" }} disabled={!dirty} onClick={save}>
            ✓ Enregistrer le workflow
          </button>
        </div>
      </div>
      <div className="card">
        <h2>Ce que voit le client</h2>
        <p className="hint" style={{ marginBottom: 12 }}>
          La piste affichée au client, déduite du workflow ci-dessus.
        </p>
        <div className="workflow" data-testid="client-track">
          {steps.map((s, i) => (
            <span key={s} style={{ display: "contents" }}>
              <span className={`ball ${i === steps.length - 1 ? "you" : "dig"}`}>{s}</span>
              {i < steps.length - 1 && <span className="muted">›</span>}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}

function Notifications() {
  const { data, setData } = useApi<Record<string, boolean | number>>("/settings/notifications");
  const { toast } = useUI();
  if (!data)
    return (
      <div className="card">
        <Loading />
      </div>
    );
  async function change(patch: Record<string, boolean | number>) {
    try {
      setData(await api("/settings/notifications", { method: "PUT", body: JSON.stringify(patch) }));
      toast("Notifications mises à jour");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Enregistrement impossible");
    }
  }
  const box = ([key, label]: [string, string]) => (
    <label key={key} style={{ display: "flex", gap: 10, alignItems: "center", padding: "6px 0" }}>
      <input type="checkbox" checked={Boolean(data[key])} onChange={(e) => change({ [key]: e.target.checked })} /> {label}
      {key === "client_reminder" && (
        <span className="hint">
          après{" "}
          <input
            className="fin-in"
            type="number"
            min={1}
            max={30}
            style={{ width: 56 }}
            aria-label="Jours avant rappel"
            value={Number(data.reminder_days)}
            onChange={(e) => Number(e.target.value) > 0 && change({ reminder_days: Number(e.target.value) })}
          />{" "}
          jours
        </span>
      )}
    </label>
  );
  return (
    <>
      <div className="card">
        <h2>Notifications au client</h2>
        <p className="hint" style={{ marginBottom: 10 }}>
          Uniquement quand ça le concerne ; jamais pour une tâche interne.
        </p>
        {CLIENT_NOTIFS.map(box)}
      </div>
      <div className="card">
        <h2>Notifications à l'équipe</h2>
        {TEAM_NOTIFS.map(box)}
      </div>
    </>
  );
}
