import { useMe } from "../../auth/AuthContext";
import { Empty, HealthBadge, Loading } from "../../components/bits";
import ReqRow from "../../components/ReqRow";
import { useUI } from "../../components/UIContext";
import { ApiError, post } from "../../lib/api";
import { fmtD, fmtDT, fmtE } from "../../lib/format";
import { healthOf, progressOf } from "../../lib/health";
import { useApi } from "../../lib/hooks";
import type { Milestone, Project, Ticket, TicketEvent } from "../../lib/types";
import type { Scope } from "./ClientSpace";

type Activity = TicketEvent & { ticket: { id: number; ref: string; title: string } };

function Ring({ pct, label }: { pct: number; label: string }) {
  const r = 64;
  const c = 2 * Math.PI * r;
  return (
    <div className="ring">
      <svg viewBox="0 0 150 150">
        <defs>
          <linearGradient id="rg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#e04bff" />
            <stop offset="1" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
        <circle className="tr" cx="75" cy="75" r={r} />
        <circle className="pr" cx="75" cy="75" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
      </svg>
      <div className="lbl">
        <b>{pct}%</b>
        <span>{label}</span>
      </div>
    </div>
  );
}

/** Version en cours : celle qui couvre aujourd'hui, sinon la prochaine. */
function currentMilestone(list: Milestone[] | undefined): Milestone | undefined {
  const today = new Date().toISOString().slice(0, 10);
  return (
    list?.find((m) => (m.starts_on ?? "") <= today && today <= (m.ends_on ?? "9999")) ??
    list?.find((m) => (m.starts_on ?? "") > today)
  );
}

export default function ClientHome({
  tickets,
  scope,
  onScope,
}: {
  tickets: Ticket[] | null;
  scope: Scope;
  onScope: (s: Scope) => void;
}) {
  const me = useMe();
  const { openTicket, toast, bump } = useUI();
  const multi = scope === "all";
  const ringProject = multi ? me.projects[0].key : scope;
  const project = useApi<Project>(`/projects/${ringProject}`);
  const portfolio = useApi<Project[]>(multi ? "/projects" : null);
  const activity = useApi<Activity[]>(`/activity${multi ? "" : `?project=${scope}`}`);

  if (!tickets) return <Loading />;
  const open = tickets.filter((t) => !t.is_closed);
  const yours = open.filter((t) => t.ball === "client");
  const atDigitalia = open.filter((t) => t.ball === "digitalia").sort((a, b) => (a.due_on ?? "9").localeCompare(b.due_on ?? "9"));
  const delivered = tickets.filter((t) => t.client_label === "Livrée").length;
  const late = open.filter((t) => t.is_late).length;
  const h = healthOf(tickets);
  const ms = currentMilestone(project.data?.milestones);
  const msTickets = tickets.filter((t) => ms && t.milestone?.id === ms.id);
  const greet = new Date().getHours() < 18 ? "Bonjour" : "Bonsoir";

  async function accept(t: Ticket) {
    try {
      await post(`/tickets/${t.id}/transition`, { to: "termine" });
      toast("Merci ! Demande livrée");
      bump();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Action impossible");
    }
  }

  return (
    <>
      <section className="hero">
        <div>
          <HealthBadge health={h.health} />
          <h1>
            {greet} {me.first_name}
            {yours.length
              ? `, ${yours.length} demande${yours.length > 1 ? "s attendent" : " attend"} votre retour`
              : ", rien ne vous attend"}
          </h1>
          <p className="sub">
            {multi ? `Sur vos ${me.projects.length} projets : ` : ""}
            {h.reason.toLowerCase()}. {atDigitalia.length} demande
            {atDigitalia.length > 1 ? "s" : ""} en cours chez Digitalia.
          </p>
          <div className="kpis">
            <div>
              <b className="neon">{yours.length}</b>à vous
            </div>
            <div>
              <b>{atDigitalia.length}</b>chez Digitalia
            </div>
            <div>
              <b>{delivered}</b>livrées
            </div>
            <div>
              <b className={late ? "rose" : ""}>{late}</b>en retard
            </div>
          </div>
        </div>
        {ms && <Ring pct={progressOf(msTickets)} label={`${ms.name} · ${fmtD(ms.ends_on)}`} />}
      </section>

      {multi && portfolio.data && (
        <div className="g3" style={{ marginBottom: 22 }}>
          {portfolio.data.map((p) => (
            <div className="ph" key={p.key} role="button" tabIndex={0} onClick={() => onScope(p.key)}>
              <HealthBadge health={p.health} style={{ position: "absolute", right: 14, top: 14 }} />
              <h2>{p.name}</h2>
              <div className="c">{p.description}</div>
              <div className="prog">
                <i style={{ width: `${progressOf(tickets.filter((t) => t.project === p.key))}%` }} />
              </div>
              <div className="row">
                <div>
                  <b style={p.counts.client ? { color: "var(--neon)" } : undefined}>{p.counts.client}</b>à vous
                </div>
                <div>
                  <b>{p.counts.digitalia}</b>chez Digitalia
                </div>
                <div>
                  <b>{p.counts.delivered}</b>livrées
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {yours.length > 0 && (
        <div style={{ marginBottom: 22 }}>
          <h2 style={{ marginBottom: 10 }}>À vous de jouer</h2>
          {yours.map((t) => {
            const test = t.status === "test";
            const quote = t.status === "devis";
            return (
              <div key={t.id} className={`act ${test ? "" : "q"}`}>
                <div className="ico">{test ? "🧪" : quote ? "📄" : "💬"}</div>
                <div>
                  <div className="t">
                    {test ? "Tester" : quote ? "Valider la proposition" : "Répondre"} · {t.title}
                  </div>
                  <div className="d">
                    {quote
                      ? `Proposition commerciale${t.quote ? ` de ${fmtE(t.quote.amount_ht)} HT` : ""} — le développement démarre dès votre accord.`
                      : test
                        ? "C'est prêt : dites-nous si ça fonctionne comme attendu."
                        : "Digitalia attend votre retour."}
                    {t.due_on ? ` · avant le ${fmtD(t.due_on)}` : ""}
                    {multi ? ` · ${t.project_name}` : ""}
                  </div>
                </div>
                <div className="bt">
                  {test ? (
                    <>
                      <button className="btn neon sm" onClick={() => accept(t)}>
                        ✓ C'est bon
                      </button>
                      <button className="btn rose sm" onClick={() => openTicket(t.id, "testko")}>
                        ✕ Pas OK
                      </button>
                    </>
                  ) : (
                    <button className="btn white sm" onClick={() => openTicket(t.id)}>
                      {quote ? "Voir la proposition" : "Répondre"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="g2">
        <div className="card">
          <h2>
            En cours chez Digitalia <span className="cnt">{atDigitalia.length}</span>
          </h2>
          {atDigitalia.length ? (
            atDigitalia.map((t) => <ReqRow key={t.id} ticket={t} showProject={multi} />)
          ) : (
            <Empty title="Rien en cours">Déposez une demande, elle apparaîtra ici.</Empty>
          )}
        </div>
        <div className="card">
          <h2>Ce qui a bougé</h2>
          <div className="feed">
            {(activity.data ?? []).slice(0, 8).map((e) => (
              <div className="fe" key={e.id}>
                <div className="l">
                  <i className={e.kind === "status" ? "v" : e.kind === "created" ? "n" : ""} />
                </div>
                <div className="b">
                  <b>{e.actor?.name ?? "Orbit"}</b>{" "}
                  {e.kind === "status"
                    ? `→ ${e.message.split("→").pop()?.trim()}`
                    : e.kind === "created"
                      ? "a déposé"
                      : "a écrit"}{" "}
                  · <a onClick={() => openTicket(e.ticket.id)}>{e.ticket.title}</a>
                  <div className="when">{fmtDT(e.at)}</div>
                </div>
              </div>
            ))}
            {activity.data?.length === 0 && <Empty title="Rien de neuf" />}
          </div>
        </div>
      </div>
    </>
  );
}
