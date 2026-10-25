import { ApiError, api } from "../lib/api";
import { fmtD, fmtE } from "../lib/format";
import { num, type ProjectFinance } from "../lib/finance";
import { useApi } from "../lib/hooks";
import { Empty, Loading } from "./bits";
import { MonthBars } from "./FinanceBits";
import { useUI } from "./UIContext";

const QUOTE_STATUS: Record<string, [string, string]> = {
  sent: ["dig", "Envoyé"],
  accepted: ["you", "Accepté"],
  refused: ["late", "Refusé"],
  draft: ["done", "Brouillon"],
};

/** Onglet Finances d'un projet (admin) — maquette « projFin ». */
export default function ProjectFinanceTab({ projectKey }: { projectKey: string }) {
  const { data: f, reload } = useApi<ProjectFinance>(`/finance/projects/${projectKey}`);
  const { toast, openTicket } = useUI();
  if (!f) return <Loading />;
  const s = f.summary;
  const current = f.months[5]?.month;

  async function toggle(url: string, is_paid: boolean) {
    try {
      await api(url, { method: "PATCH", body: JSON.stringify({ is_paid }) });
      reload();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Mise à jour impossible");
    }
  }
  const lines = [
    ...f.installments.map((e) => ({ ...e, label: "Développement", url: `/finance/projects/${projectKey}/installments/${e.id}` })),
    ...f.quotes
      .filter((q) => q.status === "accepted")
      .flatMap((q) =>
        q.installments.map((e) => ({
          ...e,
          label: q.ticket.title,
          url: `/finance/quotes/${q.id}/installments/${e.id}`,
        })),
      ),
  ].sort((a, b) => a.due_on.localeCompare(b.due_on));

  return (
    <>
      <div className="hero" style={{ gridTemplateColumns: "1fr" }}>
        <div>
          <span className="hint">Depuis le début du projet</span>
          <h1 style={{ fontSize: 44, color: "var(--neon)" }}>{fmtE(s.total)}</h1>
          <p className="sub">
            encaissés
            {s.has_cost && (
              <>
                {" "}
                · {fmtE(s.cost)} de coûts ·{" "}
                <b style={{ color: num(s.margin) >= 0 ? "var(--neon)" : "var(--rose)" }}>{fmtE(s.margin)} de marge</b>
              </>
            )}
            . Encore <b>{fmtE(s.to_come)}</b> à encaisser
            {num(s.pending_quotes) > 0 && (
              <>
                {" "}
                et <b style={{ color: "var(--amber)" }}>{fmtE(s.pending_quotes)}</b> de devis en attente
              </>
            )}
            .
          </p>
          <div className="kpis">
            <div>
              <b>{fmtE(s.dev_paid)}</b>développement <span className="muted">/ {fmtE(s.dev_total)}</span>
            </div>
            <div>
              <b className="neon">{fmtE(s.licence)}</b>licence · {s.licence_months} mois
            </div>
            <div>
              <b>{fmtE(s.quotes_paid)}</b>évolutions vendues
            </div>
            <div>
              <b>{fmtE(s.licence_monthly)}</b>par mois en récurrent
            </div>
          </div>
        </div>
      </div>
      <div className="g2">
        <div className="card">
          <h2>Recettes des 12 mois autour d'aujourd'hui</h2>
          <MonthBars
            months={f.months.map((m) => ({ month: m.month, revenue: num(m.revenue), cost: num(m.cost) }))}
            current={current}
            showCost={s.has_cost}
          />
        </div>
        <div>
          <div className="card">
            <h2>Échéances</h2>
            {lines.length ? (
              lines.map((e) => (
                <div
                  key={e.url}
                  style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "center",
                    padding: "7px 0",
                    borderBottom: "1px solid var(--line2)",
                  }}
                >
                  <button
                    className={`ball ${e.is_paid ? "you" : "done"}`}
                    style={{ minWidth: 90, justifyContent: "center", border: 0, cursor: "pointer" }}
                    title="Cliquer pour changer"
                    onClick={() => toggle(e.url, !e.is_paid)}
                  >
                    {e.is_paid ? "Encaissée" : "À venir"}
                  </button>
                  <div style={{ flex: 1 }}>
                    <b>{fmtE(e.amount)}</b>
                    <div className="hint">{e.label}</div>
                  </div>
                  <span className="hint">{fmtD(e.due_on)}</span>
                </div>
              ))
            ) : (
              <Empty title="Aucune échéance" />
            )}
          </div>
          <div className="card" style={{ marginTop: 18 }}>
            <h2>Devis</h2>
            {f.quotes.length ? (
              f.quotes.map((q) => (
                <div
                  key={q.id}
                  style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "center",
                    padding: "7px 0",
                    borderBottom: "1px solid var(--line2)",
                  }}
                >
                  <span className={`ball ${QUOTE_STATUS[q.status][0]}`} style={{ minWidth: 90, justifyContent: "center" }}>
                    {QUOTE_STATUS[q.status][1]}
                  </span>
                  <div style={{ flex: 1 }}>
                    <a onClick={() => openTicket(q.ticket.id)}>{q.ticket.title}</a>
                  </div>
                  <b>{fmtE(q.amount_ht)}</b>
                </div>
              ))
            ) : (
              <Empty title="Aucun devis" />
            )}
          </div>
        </div>
      </div>
    </>
  );
}
