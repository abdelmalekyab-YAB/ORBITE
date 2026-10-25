import { useNavigate } from "react-router-dom";
import { Avatar, Empty, HealthBadge, Loading } from "../../components/bits";
import { useUI } from "../../components/UIContext";
import { fmtD, fmtDT } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import type { Project, Ticket, TicketEvent, UserMini } from "../../lib/types";
import { Workload } from "./Team";

interface CockpitData {
  projects: Project[];
  to_handle: { key: string; label: string; tickets: Ticket[] }[];
  workload: { user: UserMini; open: number; late: number }[];
  activity: (TicketEvent & { ticket: { id: number; ref: string; title: string } })[];
}

const WHY: Record<string, string> = {
  late: "w-late",
  nouveau: "w-new",
  attente: "w-wait",
  devis: "w-wait",
  testint: "w-test",
  test: "w-test",
};

function subline(key: string, t: Ticket) {
  switch (key) {
    case "late":
      return `prévu le ${fmtD(t.due_on)}`;
    case "nouveau":
      return `nouvelle demande de ${t.author.name}`;
    case "attente":
      return `depuis le ${fmtD(t.updated_at)} — relancer ?`;
    case "testint":
      return `prêt depuis le ${fmtD(t.updated_at)}`;
    default:
      return `depuis le ${fmtD(t.updated_at)}`;
  }
}

export default function Cockpit() {
  const { data } = useApi<CockpitData>("/cockpit");
  const { openTicket } = useUI();
  const navigate = useNavigate();
  if (!data) return <Loading />;
  const todo = data.to_handle.flatMap((b) => b.tickets.map((t) => ({ b, t })));

  return (
    <>
      <h1 style={{ marginBottom: 4 }}>Cockpit</h1>
      <p className="hint" style={{ marginBottom: 18 }}>
        Santé de tous les projets et ce qui demande une action maintenant.
      </p>
      <div className="g3" style={{ marginBottom: 20 }}>
        {data.projects.map((p) => (
          <div
            className="ph"
            key={p.key}
            role="button"
            tabIndex={0}
            onClick={() => navigate(`/dig/projets/${p.key}`)}
            onKeyDown={(e) => e.key === "Enter" && navigate(`/dig/projets/${p.key}`)}
          >
            <HealthBadge health={p.health} style={{ position: "absolute", right: 14, top: 14 }} />
            <h2>{p.name}</h2>
            <div className="c">
              {p.client} · {p.lead?.name ?? "sans responsable"}
            </div>
            <div className="prog">
              <i
                style={{
                  width: `${p.counts.open + p.counts.delivered ? Math.round((p.counts.delivered / (p.counts.open + p.counts.delivered)) * 100) : 0}%`,
                }}
              />
            </div>
            <div className="why">{p.reason}</div>
            <div className="row">
              <div>
                <b>{p.counts.open}</b>ouvertes
              </div>
              <div>
                <b>{p.counts.client}</b>chez client
              </div>
              <div>
                <b className={p.counts.late ? "late" : ""}>{p.counts.late}</b>en retard
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="g2">
        <div className="card">
          <h2>
            À traiter maintenant <span className="cnt">{todo.length}</span>
          </h2>
          <div className="todo">
            {todo.length ? (
              todo.map(({ b, t }) => (
                <div
                  className="ti"
                  key={`${b.key}-${t.id}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => openTicket(t.id)}
                  onKeyDown={(e) => e.key === "Enter" && openTicket(t.id)}
                >
                  <span className={`why ${WHY[b.key]}`}>{b.label}</span>
                  <div>
                    <div className="t">
                      {t.title} <span className="muted">· {t.project_name}</span>
                    </div>
                    <div className="s">{subline(b.key, t)}</div>
                  </div>
                  <Avatar user={t.assignee} small />
                </div>
              ))
            ) : (
              <Empty title="Tout est sous contrôle" />
            )}
          </div>
        </div>
        <div>
          <div className="card">
            <h2>Charge de l'équipe</h2>
            <Workload rows={data.workload} />
          </div>
          <div className="card" style={{ marginTop: 18 }}>
            <h2>Activité récente</h2>
            <div className="feed">
              {data.activity.slice(0, 8).map((e) => (
                <div className="fe" key={e.id}>
                  <div className="l">
                    <i className={e.kind === "status" ? "v" : e.kind === "created" ? "n" : ""} />
                  </div>
                  <div className="b">
                    <b>{e.actor?.name ?? "Orbit"}</b>{" "}
                    {e.kind === "status"
                      ? e.message
                      : e.kind === "created"
                        ? "a créé"
                        : e.kind === "comment"
                          ? "a commenté"
                          : e.kind}{" "}
                    · <a onClick={() => openTicket(e.ticket.id)}>{e.ticket.ref}</a>
                    <div className="when">{fmtDT(e.at)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
