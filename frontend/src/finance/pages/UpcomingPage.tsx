import { useState } from "react";
import { finance } from "../api/client";
import type { Month } from "../api/types";
import { addMonths, currentMonth, eur, eur2, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";

/** À venir (SPEC §5.3) : reste à facturer, prévisionnel, planification, propositions. */
export function UpcomingPage({ projects }: { projects: Array<{ id: number; name: string; client_name: string }> }) {
  const [horizon, setHorizon] = useState(6);
  const { data, reload } = useApi(() => finance.upcoming(horizon), [horizon]);
  const [form, setForm] = useState({ project: "", month: addMonths(currentMonth(), 1) as Month, label: "", amount: "" });
  if (!data) return <p className="fin-sub">Chargement…</p>;
  const sum = (a: Array<{ amount?: string; remaining?: string; fixed?: string; planned?: string }>, k: "amount" | "remaining") =>
    a.reduce((s, x) => s + n(x[k]), 0);
  const plan = async (e: React.FormEvent) => {
    e.preventDefault();
    await finance.createInvoice({
      project: Number(form.project),
      service_month: form.month,
      amount: form.amount,
      label: form.label,
      status: "planned",
    });
    setForm({ ...form, label: "", amount: "" });
    reload();
  };
  return (
    <section className="fin-page">
      <div className="fin-head">
        <div>
          <h1>À venir</h1>
          <p className="fin-sub">
            Ce qu'il reste à facturer sur vos devis et contrats, et ce qui est prévu dans les prochains mois.
          </p>
        </div>
        <div className="fin-seg">
          {[3, 6, 12].map((h) => (
            <button key={h} aria-pressed={horizon === h} onClick={() => setHorizon(h)}>
              {h} mois
            </button>
          ))}
        </div>
      </div>

      <div className="fin-hero">
        <div className="fin-panel">
          <div className="fin-sub">Reste à facturer (projets validés)</div>
          <div className="fin-big fin-num">{eur.format(sum(data.remaining, "remaining"))}</div>
        </div>
        <div className="fin-stats">
          <div className="fin-stat">
            <b className="fin-num">{eur.format(data.forecast.reduce((s, f) => s + n(f.fixed) + n(f.planned), 0))}</b>
            <span>Prévu d'ici {monthLabel(data.forecast[data.forecast.length - 1].month)}</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num fin-warn">{eur.format(n(data.forecast[0].fixed) + n(data.forecast[0].planned))}</b>
            <span>À facturer en {monthLabel(data.forecast[0].month)}</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{eur.format(data.remaining.reduce((s, r) => s + n(r.unplanned), 0))}</b>
            <span>Devis pas encore planifié</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{eur.format(data.proposals.reduce((s, p) => s + n(p.value), 0))}</b>
            <span>{data.proposals.length} proposition(s) en attente</span>
          </div>
        </div>
      </div>

      <div className="fin-panel">
        <h2>Prévisionnel</h2>
        <table className="fin-table">
          <thead>
            <tr>
              <th>Mois</th>
              <th className="r">Fixe</th>
              <th className="r">Factures planifiées</th>
              <th className="r">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.forecast.map((f) => (
              <tr key={f.month}>
                <td style={{ textTransform: "capitalize" }}>{monthLabel(f.month)}</td>
                <td className="r fin-num">{eur.format(n(f.fixed))}</td>
                <td className="r fin-num">{eur.format(n(f.planned))}</td>
                <td className="r fin-num">
                  <b>{eur.format(n(f.fixed) + n(f.planned))}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="fin-panel">
        <h2>Planifier une facture</h2>
        <form className="fin-row" onSubmit={plan}>
          <label>
            Projet
            <select required value={form.project} onChange={(e) => setForm({ ...form, project: e.target.value })}>
              <option value="">—</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.client_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Mois prévu
            <input
              type="month"
              required
              value={form.month}
              onChange={(e) => setForm({ ...form, month: e.target.value as Month })}
            />
          </label>
          <label>
            Libellé
            <input
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="Ex. Acompte 30 %, solde…"
            />
          </label>
          <label>
            Montant €
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
            />
          </label>
          <button className="fin-btn" type="submit">
            Planifier
          </button>
        </form>
      </div>

      <div className="fin-panel">
        <h2>Propositions en attente de validation</h2>
        <p className="fin-sub">Non comptées dans le reste à facturer tant que le client n'a pas validé.</p>
        {data.proposals.length ? (
          <table className="fin-table">
            <thead>
              <tr>
                <th>Projet</th>
                <th>Envoyée</th>
                <th className="r">Montant</th>
              </tr>
            </thead>
            <tbody>
              {data.proposals.map((p) => (
                <tr key={p.project.id}>
                  <td>
                    <b>{p.project.name}</b>
                  </td>
                  <td>il y a {p.waiting_months} mois</td>
                  <td className="r fin-num">
                    <b>
                      {p.project.billing_type === "fixed"
                        ? `${eur.format(n(p.project.monthly_amount))} / mois`
                        : eur.format(n(p.value))}
                    </b>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="fin-empty">Aucune proposition en attente.</p>
        )}
      </div>

      <div className="fin-panel">
        <h2>Devis et contrats en cours</h2>
        {data.remaining.length ? (
          <table className="fin-table">
            <thead>
              <tr>
                <th>Projet</th>
                <th className="r">Total</th>
                <th className="r">Facturé</th>
                <th className="r">Planifié</th>
                <th className="r">Reste</th>
              </tr>
            </thead>
            <tbody>
              {data.remaining.map((r) => (
                <tr key={r.project.id} className={`fin-row--${r.kind}`}>
                  <td>
                    <b>{r.project.name}</b>
                    <div className="fin-prog fin-prog--small">
                      <i style={{ width: `${Math.min(100, (n(r.billed) / n(r.total)) * 100)}%` }} />
                    </div>
                  </td>
                  <td className="r fin-num">{eur.format(n(r.total))}</td>
                  <td className="r fin-num">{eur.format(n(r.billed))}</td>
                  <td className="r fin-num">{eur.format(n(r.planned))}</td>
                  <td className="r fin-num">
                    <b>{eur.format(n(r.remaining))}</b>
                    {n(r.unplanned) > 0 && <div className="fin-sub fin-warn">{eur.format(n(r.unplanned))} non planifié</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="fin-empty">Rien en cours.</p>
        )}
      </div>

      <div className="fin-panel">
        <h2>Factures planifiées</h2>
        {data.planned.length ? (
          data.planned.map((i) => (
            <div className="fin-entry" key={i.id}>
              <span>
                {i.due_now && <span className="fin-tag fin-tag--quote">À facturer</span>}{" "}
                <b style={{ textTransform: "capitalize" }}>{monthLabel(i.service_month)}</b> · {i.project.name}{" "}
                <span className="fin-sub">{i.label}</span>
              </span>
              <span className="fin-num">
                {eur2.format(n(i.amount))}{" "}
                {i.due_now && (
                  <button
                    className="fin-link"
                    onClick={async () => {
                      await finance.markIssued(i.id);
                      reload();
                    }}
                  >
                    marquer facturée
                  </button>
                )}
                <button
                  className="fin-link fin-link--danger"
                  onClick={async () => {
                    await finance.deleteInvoice(i.id);
                    reload();
                  }}
                >
                  retirer
                </button>
              </span>
            </div>
          ))
        ) : (
          <p className="fin-empty">Aucune facture planifiée.</p>
        )}
      </div>
    </section>
  );
}
