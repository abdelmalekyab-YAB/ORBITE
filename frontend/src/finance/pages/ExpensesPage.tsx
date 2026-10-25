import { useState } from "react";
import { finance } from "../api/client";
import type { Month } from "../api/types";
import { addMonths, currentMonth, eur, eur2, fmtDate, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";

const CATS = [
  "Sous-traitance",
  "Logiciels & abonnements",
  "Hébergement & serveurs",
  "Matériel informatique",
  "Télécom & internet",
  "Déplacements",
  "Repas & réceptions",
  "Honoraires (comptable, juridique)",
  "Frais bancaires",
  "Marketing & communication",
  "Formation",
  "Fournitures",
  "Autres",
];

/** Dépenses avec justificatifs (SPEC §5.5). */
export function ExpensesPage({ projects }: { projects: Array<{ id: number; name: string; client_name: string }> }) {
  const [month, setMonth] = useState<Month>(currentMonth());
  const { data, reload } = useApi(() => finance.expenses(month), [month]);
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    if (!fd.get("project")) fd.delete("project");
    if (!(fd.get("receipt") as File)?.size) fd.delete("receipt");
    await finance.createExpense(fd);
    e.currentTarget.reset();
    reload();
  };
  const list = data ?? [];
  const ht = list.reduce((s, x) => s + n(x.amount_ht), 0);
  const tva = list.reduce((s, x) => s + n(x.vat), 0);
  const byCat = Object.entries(
    list.reduce<Record<string, number>>((a, x) => ({ ...a, [x.category]: (a[x.category] || 0) + n(x.amount_ht) }), {}),
  ).sort((a, b) => b[1] - a[1]);
  return (
    <section className="fin-page">
      <div className="fin-head">
        <div>
          <h1>Dépenses</h1>
          <p className="fin-sub">Notez vos dépenses avec leur justificatif. Rattachées à un projet, elles alimentent sa marge.</p>
        </div>
        <div className="fin-monthnav">
          <button className="fin-btn fin-btn--ghost fin-btn--small" onClick={() => setMonth(addMonths(month, -1))}>
            ‹
          </button>
          <strong style={{ textTransform: "capitalize" }}>{monthLabel(month)}</strong>
          <button className="fin-btn fin-btn--ghost fin-btn--small" onClick={() => setMonth(addMonths(month, 1))}>
            ›
          </button>
        </div>
      </div>
      <div className="fin-panel">
        <h2>Nouvelle dépense</h2>
        <form onSubmit={submit} className="fin-form">
          <div className="fin-row">
            <label>
              Date
              <input name="date" type="date" required defaultValue={`${month}-01`} />
            </label>
            <label>
              Fournisseur
              <input name="supplier" required />
            </label>
            <label>
              Catégorie
              <select name="category">
                {CATS.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="fin-row">
            <label>
              Description
              <input name="label" />
            </label>
            <label>
              Projet (optionnel)
              <select name="project">
                <option value="">Frais généraux</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.client_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="fin-row">
            <label>
              Montant HT (€)
              <input name="amount_ht" type="number" step="0.01" min="0" required />
            </label>
            <label>
              TVA (€)
              <input name="vat" type="number" step="0.01" min="0" defaultValue="0" />
            </label>
            <label>
              Justificatif
              <input name="receipt" type="file" accept=".pdf,image/*" />
            </label>
            <button className="fin-btn" type="submit">
              Ajouter la dépense
            </button>
          </div>
        </form>
      </div>
      <div className="fin-two">
        <div className="fin-panel">
          <div className="fin-head">
            <h2>Dépenses de {monthLabel(month)}</h2>
            <span className="fin-num">
              <b>{list.length ? eur2.format(ht) + " HT" : ""}</b>
            </span>
          </div>
          {list.length ? (
            <table className="fin-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Fournisseur</th>
                  <th>Projet</th>
                  <th className="r">HT</th>
                  <th className="r">TVA</th>
                  <th>Justificatif</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.map((x) => (
                  <tr key={x.id}>
                    <td>{fmtDate(x.date)}</td>
                    <td>
                      <b>{x.supplier}</b>
                      <div className="fin-sub">
                        {x.category}
                        {x.label ? ` · ${x.label}` : ""}
                      </div>
                    </td>
                    <td className="fin-sub">{x.project ? projects.find((p) => p.id === x.project)?.name : "Frais généraux"}</td>
                    <td className="r fin-num">{eur2.format(n(x.amount_ht))}</td>
                    <td className="r fin-num">{n(x.vat) ? eur2.format(n(x.vat)) : "—"}</td>
                    <td>
                      {x.receipt_url ? (
                        <a className="fin-clip" href={x.receipt_url} target="_blank" rel="noreferrer">
                          📎 {x.receipt_name}
                        </a>
                      ) : (
                        <span className="fin-missing">Manquant</span>
                      )}
                    </td>
                    <td>
                      <button
                        className="fin-link fin-link--danger"
                        onClick={async () => {
                          await finance.deleteExpense(x.id);
                          reload();
                        }}
                      >
                        retirer
                      </button>
                    </td>
                  </tr>
                ))}
                <tr className="fin-total">
                  <td colSpan={3}>Total</td>
                  <td className="r fin-num">{eur2.format(ht)}</td>
                  <td className="r fin-num">{tva ? eur2.format(tva) : "—"}</td>
                  <td colSpan={2} />
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="fin-empty">Aucune dépense en {monthLabel(month)}.</p>
          )}
        </div>
        <div className="fin-panel">
          <h2>Par catégorie</h2>
          <ul className="fin-cats">
            {byCat.length ? (
              byCat.map(([c, v]) => (
                <li key={c}>
                  <span>{c}</span>
                  <b className="fin-num">{eur.format(v)}</b>
                </li>
              ))
            ) : (
              <li className="fin-sub">—</li>
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
