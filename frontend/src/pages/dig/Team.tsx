import { Avatar, Empty, Loading, TypeTag } from "../../components/bits";
import { useUI } from "../../components/UIContext";
import { fmtD } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import type { Ticket, UserMini } from "../../lib/types";

export interface TeamData {
  members: { user: UserMini & { email: string }; open: number; late: number; tickets: Ticket[] }[];
  unassigned: number;
}

export function useMembers() {
  const { data } = useApi<TeamData>("/team");
  return (data?.members ?? []).map((m) => ({ id: m.user.id, name: m.user.name }));
}

/** Barres de charge (composant `load` de la maquette). */
export function Workload({ rows }: { rows: { user: UserMini; open: number; late: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.open));
  return (
    <div className="load">
      {rows.map((r) => (
        <div className="r" key={r.user.id}>
          <Avatar user={r.user} />
          <b>
            {r.user.name}
            {r.late ? <span className="late"> · {r.late} en retard</span> : null}
          </b>
          <div className="prog">
            <i style={{ width: `${(r.open / max) * 100}%` }} />
          </div>
          <span className="n">{r.open}</span>
        </div>
      ))}
    </div>
  );
}

export default function Team() {
  const { data } = useApi<TeamData>("/team");
  const { openTicket } = useUI();
  if (!data) return <Loading />;
  return (
    <>
      <h1 style={{ marginBottom: 18 }}>Équipe</h1>
      <div className="g2">
        <div>
          {data.members.map((m) => (
            <div className="card" key={m.user.id} style={{ marginBottom: 16 }}>
              <h2>
                <Avatar user={m.user} /> {m.user.name}{" "}
                <span className="cnt">
                  {m.open} en cours · {m.late} en retard
                </span>
              </h2>
              {m.tickets.length ? (
                <div className="todo">
                  {m.tickets.map((t) => (
                    <div
                      className="ti"
                      key={t.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => openTicket(t.id)}
                      onKeyDown={(e) => e.key === "Enter" && openTicket(t.id)}
                    >
                      <span
                        className={`why ${t.is_late ? "w-late" : t.status === "test" ? "w-test" : ""}`}
                        style={!t.is_late && t.status !== "test" ? { background: "var(--s3)", color: "var(--ink2)" } : undefined}
                      >
                        {t.is_late ? "En retard" : t.status_label}
                      </span>
                      <div>
                        <div className="t">{t.title}</div>
                        <div className="s">
                          {t.project_name} · {t.due_on ? `prévu le ${fmtD(t.due_on)}` : "sans date"}
                        </div>
                      </div>
                      <TypeTag type={t.type} />
                    </div>
                  ))}
                </div>
              ) : (
                <Empty title="Rien d'assigné" />
              )}
            </div>
          ))}
        </div>
        <div className="card">
          <h2>Répartition</h2>
          <Workload rows={data.members} />
          {data.unassigned > 0 && (
            <p className="hint" style={{ marginTop: 14 }}>
              {data.unassigned} ticket(s) ouvert(s) sans responsable.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
