import { useRef, useState } from "react";
import { finance } from "../api/client";
import type { Month, MonthRow, PaymentUpdate } from "../api/types";
import { PayChip } from "../components/PayChip";
import { PaymentDialog } from "../components/PaymentDialog";
import { addMonths, currentMonth, eur2, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";

/** Saisie du mois (SPEC §5.2). */
export function MonthPage() {
  const [month, setMonth] = useState<Month>(currentMonth());
  const { data, loading, reload } = useApi(() => finance.month(month), [month]);
  const [pay, setPay] = useState<{
    title: string;
    initial: PaymentUpdate & { due_date: string | null; paid_on: string | null };
    save: (u: PaymentUpdate) => Promise<unknown>;
  } | null>(null);
  const [adjust, setAdjust] = useState<{ row: MonthRow; value: string } | null>(null);
  const fileTarget = useRef<((f: File) => Promise<unknown>) | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pick = (cb: (f: File) => Promise<unknown>) => {
    fileTarget.current = cb;
    fileInput.current?.click();
  };
  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f && fileTarget.current) {
      await fileTarget.current(f);
      reload();
    }
  };
  const addInvoice = async (e: React.FormEvent<HTMLFormElement>, projectId: number) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    await finance.createInvoice({
      project: projectId,
      service_month: month,
      amount: String(fd.get("amount")),
      label: String(fd.get("label") || ""),
      status: "issued",
    });
    e.currentTarget.reset();
    reload();
  };

  return (
    <section className="fin-page">
      <div className="fin-head">
        <div>
          <h1>Saisie du mois</h1>
          <p className="fin-sub">Les montants fixes se remplissent seuls. Ajoutez les factures sur devis.</p>
        </div>
        <div className="fin-monthnav">
          <button
            className="fin-btn fin-btn--ghost fin-btn--small"
            onClick={() => setMonth(addMonths(month, -1))}
            aria-label="Mois précédent"
          >
            ‹
          </button>
          <strong style={{ textTransform: "capitalize" }}>{monthLabel(month)}</strong>
          <button
            className="fin-btn fin-btn--ghost fin-btn--small"
            onClick={() => setMonth(addMonths(month, 1))}
            aria-label="Mois suivant"
          >
            ›
          </button>
        </div>
      </div>
      <input ref={fileInput} type="file" accept=".pdf,image/*" hidden onChange={onFile} />

      <div className="fin-panel">
        {loading && !data ? (
          <p className="fin-sub">Chargement…</p>
        ) : !data?.rows.length ? (
          <p className="fin-empty">Aucun projet actif en {monthLabel(month)}.</p>
        ) : (
          <table className="fin-table">
            <thead>
              <tr>
                <th>Projet</th>
                <th>Facturation</th>
                <th className="r">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => {
                const p = row.project;
                const pid = Number(p.id);
                const f = row.fixed;
                return (
                  <tr key={p.id} className={`fin-row--${p.billing_type}`}>
                    <td>
                      <b>{p.name}</b>
                      <span className={`fin-tag fin-tag--${p.billing_type}`}>
                        {p.billing_type === "fixed" ? "Fixe" : "Sur devis"}
                      </span>
                    </td>
                    <td>
                      {f && (
                        <div className="fin-entry">
                          <span>
                            {f.future ? (
                              "Prévu"
                            ) : f.is_current ? (
                              f.billed ? (
                                "Montant fixe · facturé"
                              ) : (
                                <span className="fin-warn">À facturer ce mois</span>
                              )
                            ) : f.adjusted ? (
                              "Ajusté ce mois"
                            ) : (
                              "Montant fixe · auto"
                            )}
                            {f.adjusted && n(f.amount) === 0 ? " (non facturé)" : ""}
                          </span>
                          <span className="fin-num">
                            {!f.future && f.billed && f.pay_state && (
                              <PayChip
                                state={f.pay_state}
                                due={f.due_date}
                                paidOn={f.paid_on}
                                onClick={() =>
                                  setPay({
                                    title: `${p.name} · ${monthLabel(month)}`,
                                    initial: {
                                      payment_status:
                                        f.pay_state === "paid" ? "paid" : f.pay_state === "late" ? "late" : "pending",
                                      due_date: f.due_date,
                                      paid_on: f.paid_on,
                                    },
                                    save: (u) => finance.fixedPayment(pid, month, u),
                                  })
                                }
                              />
                            )}
                            {f.has_document ? <span className="fin-clip">📎 {f.document_name}</span> : null}
                            {!f.future && f.billed && (
                              <button
                                className="fin-link"
                                onClick={() => pick((file) => finance.fixedDocument(pid, month, file))}
                              >
                                {f.has_document ? "remplacer" : "joindre la facture"}
                              </button>
                            )}{" "}
                            {eur2.format(n(f.amount))}
                            <button className="fin-link" onClick={() => setAdjust({ row, value: f.amount })}>
                              {f.adjusted ? "modifier" : "ajuster"}
                            </button>
                            {f.is_current && (
                              <button
                                className="fin-link"
                                onClick={async () => {
                                  await finance.fixedMark(pid, month, !f.billed);
                                  reload();
                                }}
                              >
                                {f.billed ? "annuler" : "marquer facturé"}
                              </button>
                            )}
                          </span>
                        </div>
                      )}
                      {row.invoices.map((i) => (
                        <div className="fin-entry" key={i.id}>
                          <span>
                            {i.pending && (
                              <span className="fin-tag fin-tag--quote">
                                {month <= data.current_month ? "À facturer" : "Prévue"}
                              </span>
                            )}
                            {i.kind === "deposit" && <span className="fin-tag fin-tag--fixed">Démarrage</span>}{" "}
                            {i.label || "Facture"}
                          </span>
                          <span className="fin-num">
                            {!i.pending && i.pay_state && (
                              <PayChip
                                state={i.pay_state}
                                due={i.due_date}
                                paidOn={i.paid_on}
                                onClick={() =>
                                  setPay({
                                    title: `${p.name} · ${i.label}`,
                                    initial: {
                                      payment_status:
                                        i.pay_state === "paid" ? "paid" : i.pay_state === "late" ? "late" : "pending",
                                      due_date: i.due_date,
                                      paid_on: i.paid_on,
                                    },
                                    save: (u) => finance.invoicePayment(i.id, u),
                                  })
                                }
                              />
                            )}
                            {i.has_document && <span className="fin-clip">📎 {i.document_name}</span>}
                            {!i.pending && (
                              <button className="fin-link" onClick={() => pick((file) => finance.invoiceDocument(i.id, file))}>
                                {i.has_document ? "remplacer" : "joindre"}
                              </button>
                            )}{" "}
                            {eur2.format(n(i.amount))}
                            {i.pending && month <= data.current_month && (
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
                            {!i.pending && month === data.current_month && (
                              <button
                                className="fin-link"
                                onClick={async () => {
                                  await finance.markPlanned(i.id);
                                  reload();
                                }}
                              >
                                remettre à facturer
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
                      ))}
                      <form className="fin-inline" onSubmit={(e) => addInvoice(e, pid)}>
                        <input
                          name="label"
                          placeholder={p.billing_type === "fixed" ? "Supplément (libellé)" : "N° facture / n° commande / libellé"}
                        />
                        <input name="amount" type="number" step="0.01" min="0" placeholder="Montant €" required />
                        <button className="fin-btn fin-btn--small" type="submit">
                          Ajouter
                        </button>
                      </form>
                    </td>
                    <td className="r fin-num">
                      <b>{eur2.format(n(row.total))}</b>
                    </td>
                  </tr>
                );
              })}
              <tr className="fin-total">
                <td colSpan={2}>
                  Total facturé {monthLabel(month)}
                  {n(data.to_bill) > 0 && (
                    <div className="fin-sub fin-warn">+ {eur2.format(n(data.to_bill))} encore à facturer ce mois</div>
                  )}
                </td>
                <td className="r fin-num">{eur2.format(n(data.total))}</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      {adjust && (
        <dialog open className="fin-dialog">
          <h2>
            {adjust.row.project.name} · {monthLabel(month)}
          </h2>
          <p className="fin-sub">
            Montant fixe habituel : {eur2.format(n(adjust.row.project.monthly_amount))}. Mettez 0 si ce mois n'est pas facturé.
          </p>
          <label>
            Montant facturé ce mois (€)
            <input
              type="number"
              step="0.01"
              min="0"
              value={adjust.value}
              onChange={(e) => setAdjust({ ...adjust, value: e.target.value })}
            />
          </label>
          <div className="fin-row fin-row--between">
            <button
              className="fin-link"
              onClick={async () => {
                await finance.fixedAdjust(Number(adjust.row.project.id), month, null);
                setAdjust(null);
                reload();
              }}
            >
              Revenir au montant fixe
            </button>
            <div className="fin-row">
              <button className="fin-btn fin-btn--ghost" onClick={() => setAdjust(null)}>
                Annuler
              </button>
              <button
                className="fin-btn"
                onClick={async () => {
                  await finance.fixedAdjust(Number(adjust.row.project.id), month, Number(adjust.value));
                  setAdjust(null);
                  reload();
                }}
              >
                Enregistrer
              </button>
            </div>
          </div>
        </dialog>
      )}
      {pay && (
        <PaymentDialog
          title={pay.title}
          initial={pay.initial}
          onSave={async (u) => {
            await pay.save(u);
            reload();
          }}
          onClose={() => setPay(null)}
        />
      )}
    </section>
  );
}
