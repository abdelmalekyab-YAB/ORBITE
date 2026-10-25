import { useState } from "react";
import { finance } from "../api/client";
import type { BilledItem, Dashboard, PaymentUpdate } from "../api/types";
import { PayChip } from "../components/PayChip";
import { PaymentDialog } from "../components/PaymentDialog";
import { addMonths, clientColor, currentMonth, eur, eur2, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";

/**
 * Tableau de bord (SPEC §5.1). Un seul appel API ; chaque mutation recharge.
 * Les graphiques sont laissés au composant de charting d'Orbit (Recharts/Chart.js) : voir <Chart12/>.
 */
export function DashboardPage() {
  const { data, loading, error, reload } = useApi(() => finance.dashboard());
  const [pay, setPay] = useState<BilledItem | null>(null);
  if (loading && !data) return <p className="fin-sub">Chargement…</p>;
  if (error || !data) return <p className="fin-error">Impossible de charger le tableau de bord : {error}</p>;
  const d = data;
  const prev = n(d.prev_month_revenue),
    rev = n(d.month_revenue);
  const delta = prev ? Math.round(((rev - prev) / prev) * 100) : null;
  const planned = n(d.billed_this_month_total) + n(d.to_bill_total);
  const monthName = monthLabel(d.month).split(" ")[0];

  const savePayment = async (item: BilledItem, upd: PaymentUpdate) => {
    if (item.ref.startsWith("inv:")) await finance.invoicePayment(Number(item.ref.slice(4)), upd);
    else {
      const [pid, m] = item.ref.slice(4).split("|");
      await finance.fixedPayment(Number(pid), m as never, upd);
    }
    reload();
  };
  const markDue = async (key: string) => {
    if (key.startsWith("fix:")) await finance.fixedMark(Number(key.slice(4)), d.month, true);
    else await finance.markIssued(Number(key.slice(4)));
    reload();
  };
  const clientName = (id: string) => d.clients.find((c) => c.id === id)?.name ?? "—";
  const Row = ({ x }: { x: BilledItem }) => (
    <div className="fin-cash-item">
      <div>
        <b>{x.project.name}</b>{" "}
        <span className="fin-sub">
          · {clientName(x.project.client_id)} · {x.label}
        </span>
      </div>
      <div className="fin-num">
        <PayChip state={x.pay_state} due={x.due_date} paidOn={x.paid_on} onClick={() => setPay(x)} />{" "}
        <b>{eur2.format(n(x.amount))}</b>
      </div>
    </div>
  );

  return (
    <section className="fin-page">
      <div className="fin-row fin-row--end">
        <button className="fin-btn" onClick={() => void finance.downloadCeoPdf()}>
          Exporter en PDF pour le CEO
        </button>
      </div>

      {/* Hero */}
      <div className="fin-hero">
        <div className="fin-panel">
          <div className="fin-sub">Facturé en {monthLabel(d.month)}</div>
          <div className="fin-big fin-num">{eur.format(rev)}</div>
          <div className="fin-split">
            <span style={{ width: `${rev ? (n(d.month_fixed) / rev) * 100 : 0}%` }} className="fin-split--fixed" />
            <span className="fin-split--quote" />
          </div>
          <div className="fin-legend">
            <span>
              Fixe <b>{eur.format(n(d.month_fixed))}</b>
            </span>
            <span>
              Sur devis <b>{eur.format(n(d.month_quote))}</b>
            </span>
            {n(d.to_bill_total) > 0 && <span className="fin-warn">{eur.format(n(d.to_bill_total))} à facturer ce mois</span>}
          </div>
        </div>
        <div className="fin-stats">
          <div className="fin-stat">
            <b className="fin-num">{eur.format(n(d.ytd))}</b>
            <span>Cumul {d.month.slice(0, 4)}</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{eur.format(n(d.mrr))}</b>
            <span>Récurrent fixe / mois</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{delta === null ? "—" : `${delta >= 0 ? "+" : ""}${delta} %`}</b>
            <span>vs {monthLabel(addMonths(d.month, -1))}</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">
              {d.ranking_12.some((r) => n(r.cost)) ? eur.format(d.ranking_12.reduce((s, r) => s + n(r.margin), 0)) : "—"}
            </b>
            <span>Marge 12 mois</span>
          </div>
        </div>
      </div>

      {/* Facturation du mois (R11 + R12) */}
      <div className="fin-panel fin-panel--accent-orange">
        <div className="fin-head">
          <h2>Facturation de {monthLabel(d.month)}</h2>
          <span className="fin-num">
            {eur.format(planned)} <span className="fin-sub">prévus au total</span>
          </span>
        </div>
        <div className="fin-stats fin-stats--2">
          <div className="fin-stat fin-stat--teal">
            <b className="fin-num">{eur.format(n(d.billed_this_month_total))}</b>
            <span>Déjà facturé · {d.billed_this_month.length} facture(s)</span>
          </div>
          <div className="fin-stat fin-stat--orange">
            <b className="fin-num fin-warn">{eur.format(n(d.to_bill_total))}</b>
            <span>Encore à facturer · {d.to_bill.length} ligne(s)</span>
          </div>
        </div>
        <div className="fin-prog">
          <i style={{ width: `${planned ? (n(d.billed_this_month_total) / planned) * 100 : 0}%` }} />
        </div>
        <h3 className="fin-warn">Encore à facturer</h3>
        {d.to_bill.length ? (
          d.to_bill.map((x) => (
            <div className="fin-cash-item" key={x.key}>
              <div>
                <b>{x.project.name}</b> <span className="fin-sub">· {clientName(x.project.client_id)}</span>
                <div className="fin-sub">
                  {x.overdue_from ? `En retard (prévue en ${monthLabel(x.overdue_from)}) · ` : ""}
                  {x.label}
                </div>
              </div>
              <div className="fin-num">
                <b>{eur2.format(n(x.amount))}</b>{" "}
                <button className="fin-link" onClick={() => markDue(x.key)}>
                  marquer facturé
                </button>
              </div>
            </div>
          ))
        ) : (
          <p className="fin-sub">Tout est facturé pour ce mois 🎉</p>
        )}
        <h3 className="fin-teal">Déjà facturé ce mois</h3>
        {d.billed_this_month.length ? (
          d.billed_this_month.map((x) => <Row key={x.ref} x={x} />)
        ) : (
          <p className="fin-sub">Rien de facturé pour l'instant ce mois-ci.</p>
        )}
      </div>

      {/* À encaisser d'ici fin de mois (R16) */}
      <div className="fin-panel fin-panel--accent-teal">
        <div className="fin-head">
          <div>
            <h2>À encaisser d'ici fin {monthName}</h2>
            <div className="fin-sub">Factures émises dont l'échéance tombe ce mois-ci ou est déjà dépassée.</div>
          </div>
          <span className="fin-num fin-big-2">{eur.format(n(d.cash.expected_by_month_end))}</span>
        </div>
        {d.cash.late.length > 0 && (
          <>
            <div className="fin-cash-month fin-danger">
              <span>En retard · à relancer</span>
              <span className="fin-num">{eur2.format(n(d.cash.late_total))}</span>
            </div>
            {d.cash.late.map((x) => (
              <Row key={x.ref} x={x} />
            ))}
          </>
        )}
        {d.cash.this_month.length > 0 && (
          <>
            <div className="fin-cash-month">
              <span>Échéance en {monthLabel(d.month)}</span>
              <span className="fin-num">{eur2.format(n(d.cash.this_month_total))}</span>
            </div>
            {d.cash.this_month.map((x) => (
              <Row key={x.ref} x={x} />
            ))}
          </>
        )}
        {d.cash.no_due.length > 0 && (
          <>
            <div className="fin-cash-month fin-sub">
              <span>Échéance non renseignée · {eur2.format(n(d.cash.no_due_total))}</span>
              <span>cliquez la pastille pour la fixer</span>
            </div>
            {d.cash.no_due.map((x) => (
              <Row key={x.ref} x={x} />
            ))}
          </>
        )}
        {!d.cash.late.length && !d.cash.this_month.length && !d.cash.no_due.length && (
          <p className="fin-sub">Rien à encaisser d'ici la fin du mois : tout est payé.</p>
        )}
        {Object.keys(d.cash.later_by_month).length > 0 && (
          <details className="fin-later">
            <summary>Mois suivants · {eur.format(n(d.cash.later_total))}</summary>
            {Object.entries(d.cash.later_by_month).map(([m, items]) => (
              <div key={m}>
                <div className="fin-cash-month">
                  <span style={{ textTransform: "capitalize" }}>{monthLabel(m)}</span>
                  <span className="fin-num">{eur2.format(items.reduce((s, x) => s + n(x.amount), 0))}</span>
                </div>
                {items.map((x) => (
                  <Row key={x.ref} x={x} />
                ))}
              </div>
            ))}
          </details>
        )}
      </div>

      {/* Reste à facturer (R13) */}
      <div className="fin-panel">
        <div className="fin-head">
          <h2>Reste à facturer sur les projets validés</h2>
          <span className="fin-num fin-big-2">
            {d.remaining.length ? eur.format(d.remaining.reduce((s, r) => s + n(r.remaining), 0)) : ""}
          </span>
        </div>
        {d.remaining.length ? (
          d.remaining.map((r) => (
            <div className="fin-rank-item" key={r.project.id}>
              <div>
                <b>{r.project.name}</b> <span className="fin-sub">· {clientName(r.project.client_id)}</span>
                <div className="fin-prog fin-prog--small">
                  <i style={{ width: `${Math.min(100, (n(r.billed) / n(r.total)) * 100)}%` }} />
                </div>
                <div className="fin-sub">
                  {eur.format(n(r.billed))} facturés sur {eur.format(n(r.total))}
                  {n(r.planned) ? ` · ${eur.format(n(r.planned))} planifiés` : ""}
                  {n(r.unplanned) > 0 && r.kind === "quote" ? (
                    <>
                      {" "}
                      · <span className="fin-warn">{eur.format(n(r.unplanned))} non planifiés</span>
                    </>
                  ) : null}
                </div>
              </div>
              <div className="fin-num fin-amt">
                <b>{eur.format(n(r.remaining))}</b>
                <small>reste à facturer</small>
              </div>
            </div>
          ))
        ) : (
          <p className="fin-sub">Rien à facturer sur les projets validés.</p>
        )}
      </div>

      {/* Propositions (R14) */}
      <div className="fin-panel">
        <div className="fin-head">
          <h2>Propositions en attente de validation</h2>
          <span className="fin-num fin-big-2">
            {d.proposals.length ? eur.format(d.proposals.reduce((s, r) => s + n(r.value), 0)) : ""}
          </span>
        </div>
        {d.proposals.length ? (
          d.proposals.map((r) => (
            <div className="fin-rank-item" key={r.project.id}>
              <div>
                <b>{r.project.name}</b> <span className="fin-sub">· {clientName(r.project.client_id)}</span>
                <div className="fin-sub">
                  Envoyée en {monthLabel(r.project.start_month)}
                  {r.waiting_months ? ` · en attente depuis ${r.waiting_months} mois` : ""}
                  {r.project.note ? ` · ${r.project.note}` : ""}
                </div>
              </div>
              <div className="fin-num fin-amt">
                <b>
                  {r.project.billing_type === "fixed"
                    ? `${eur.format(n(r.project.monthly_amount))} / mois`
                    : eur.format(n(r.value))}
                </b>
              </div>
            </div>
          ))
        ) : (
          <p className="fin-sub">Aucune proposition en attente.</p>
        )}
      </div>

      {/* Évolution 12 mois — brancher le composant de charts d'Orbit */}
      <div className="fin-panel">
        <h2>Évolution sur 12 mois</h2>
        <Chart12 data={d} />
      </div>

      {/* Classement (R19) */}
      <div className="fin-panel">
        <h2>Projets les plus rentables · 12 derniers mois</h2>
        <ol className="fin-rank">
          {d.ranking_12.map((r, i) => {
            const anyCost = d.ranking_12.some((x) => n(x.cost));
            const v = anyCost ? n(r.margin) : n(r.revenue);
            const max = Math.max(1, ...d.ranking_12.map((x) => (anyCost ? Math.max(n(x.margin), 0) : n(x.revenue))));
            return (
              <li key={r.project.id}>
                <span className="fin-pos">{i + 1}</span>
                <div>
                  <b>{r.project.name}</b> <span className="fin-sub">· {clientName(r.project.client_id)}</span>
                  <div className="fin-meter">
                    <i
                      style={{
                        width: `${(Math.max(0, v) / max) * 100}%`,
                        background: clientColor(d.clients, r.project.client_id),
                      }}
                    />
                  </div>
                </div>
                <div className="fin-num fin-amt">
                  <b>{eur.format(v)}</b>
                  <small>
                    {anyCost
                      ? `CA ${eur.format(n(r.revenue))} · marge ${n(r.revenue) ? Math.round((n(r.margin) / n(r.revenue)) * 100) : 0} %`
                      : "chiffre d'affaires"}
                  </small>
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      {pay && (
        <PaymentDialog
          title={`${pay.project.name} · ${eur2.format(n(pay.amount))}`}
          hint={`${clientName(pay.project.client_id)} · ${pay.label}`}
          initial={{ payment_status: pay.payment_status, due_date: pay.due_date, paid_on: pay.paid_on }}
          onSave={(u) => savePayment(pay, u)}
          onClose={() => setPay(null)}
        />
      )}
    </section>
  );
}

/** Barres empilées par client. Version sans dépendance (SVG) ; remplacer par Recharts si Orbit l'utilise. */
function Chart12({ data }: { data: Dashboard }) {
  const months = data.chart_12;
  const W = 720,
    H = 220,
    pad = 36;
  const totals = months.map((m) => data.clients.reduce((s, c) => s + n(m[c.id]), 0));
  const max = Math.max(1, ...totals);
  const bw = (W - pad) / months.length;
  return (
    <svg viewBox={`0 0 ${W} ${H + 30}`} width="100%" role="img" aria-label="Chiffre d'affaires mensuel par client">
      {months.map((m, i) => {
        let y = H;
        return (
          <g key={m.month}>
            {data.clients.map((c) => {
              const v = n(m[c.id]);
              if (!v) return null;
              const h = (v / max) * (H - 10);
              y -= h;
              return (
                <rect key={c.id} x={pad + i * bw + 4} y={y} width={bw - 8} height={h} fill={clientColor(data.clients, c.id)}>
                  <title>
                    {c.name} · {monthLabel(m.month)} · {eur.format(v)}
                  </title>
                </rect>
              );
            })}
            <text x={pad + i * bw + bw / 2} y={H + 18} textAnchor="middle" fontSize="11" fill="currentColor" opacity=".7">
              {monthLabel(m.month, true)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export const CURRENT_MONTH = currentMonth();
