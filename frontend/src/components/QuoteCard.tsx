import { useState } from "react";
import { useMe } from "../auth/AuthContext";
import { api, post } from "../lib/api";
import { fmtD, fmtDT, fmtE, PARTS_LABEL } from "../lib/format";
import type { Quote, TicketDetail } from "../lib/types";

const STATUS_TEXT = { sent: "en attente de votre accord", accepted: "acceptée", refused: "refusée", draft: "brouillon" };

/** Carte « Proposition commerciale » de la fiche (règles 15 à 18). */
export default function QuoteCard({
  t,
  run,
  onRefuse,
}: {
  t: TicketDetail;
  run: (action: () => Promise<TicketDetail>, done?: string) => Promise<boolean>;
  onRefuse: () => void;
}) {
  const me = useMe();
  const q = t.quote_detail;
  const canEdit = me.is_digitalia && (me.job === "pm" || me.job === "admin");
  const [editing, setEditing] = useState(false);
  if (!q) return null;

  const statusText =
    me.is_digitalia && q.status === "sent"
      ? "envoyée, en attente du client"
      : !me.is_digitalia && q.status === "draft"
        ? "en cours d'ajustement par Digitalia"
        : STATUS_TEXT[q.status];

  return (
    <div className="card tight" style={{ borderColor: "rgba(255,193,77,.45)" }} data-testid="quote-card">
      <h3 style={{ marginBottom: 8, color: "var(--amber)" }}>Proposition commerciale · {statusText}</h3>
      {editing ? (
        <QuoteForm
          quote={q}
          onCancel={() => setEditing(false)}
          onSave={async (values) => {
            const ok = await run(async () => {
              await api(`/tickets/${t.id}/quote`, { method: "PATCH", body: JSON.stringify(values) });
              return post<TicketDetail>(`/tickets/${t.id}/quote/send`, {});
            }, "Proposition modifiée et renvoyée");
            if (ok) setEditing(false);
          }}
        />
      ) : (
        <>
          <div style={{ fontFamily: "'Space Grotesk'", fontSize: 28, fontWeight: 700, letterSpacing: "-.02em" }}>
            {fmtE(q.amount_ht)}{" "}
            <span className="hint" style={{ fontFamily: "Inter", fontSize: 13 }}>
              HT · {PARTS_LABEL[q.parts]}
            </span>
          </div>
          <div className="desc" style={{ marginTop: 8 }}>
            {q.description || <span className="hint">Pas de détail.</span>}
          </div>
          <div className="hint" style={{ marginTop: 8 }}>
            {q.sent_at && <>Envoyée le {fmtDT(q.sent_at)}</>}
            {q.decided_at && <> · réponse le {fmtDT(q.decided_at)}</>}
            {q.pdf && (
              <>
                {" "}
                ·{" "}
                <a href={q.pdf} target="_blank" rel="noreferrer">
                  📎 devis.pdf
                </a>
              </>
            )}
          </div>
        </>
      )}

      {!editing && q.status === "sent" && !me.is_digitalia && (
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button
            className="btn neon"
            onClick={() => run(() => post<TicketDetail>(`/tickets/${t.id}/quote/accept`, {}), "Proposition acceptée — merci !")}
          >
            ✓ J'accepte la proposition
          </button>
          <button className="btn rose" onClick={onRefuse}>
            Refuser
          </button>
          <span className="hint" style={{ alignSelf: "center" }}>
            ou posez une question dans la discussion
          </span>
        </div>
      )}
      {!editing && me.is_digitalia && (q.status === "sent" || q.status === "draft") && (
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {q.status === "sent" && (
            <button
              className="btn sm"
              onClick={() =>
                run(
                  () =>
                    post<TicketDetail>(`/tickets/${t.id}/ping`, {
                      body: "Petite relance : avez-vous pu regarder notre proposition ?",
                    }),
                  "Client relancé",
                )
              }
            >
              Relancer le client
            </button>
          )}
          {canEdit && (
            <button className="btn sm" onClick={() => setEditing(true)}>
              Modifier la proposition
            </button>
          )}
          {canEdit && q.status === "draft" && (
            <button
              className="btn grad sm"
              onClick={() => run(() => post<TicketDetail>(`/tickets/${t.id}/quote/send`, {}), "Proposition envoyée")}
            >
              Renvoyer
            </button>
          )}
        </div>
      )}
      {q.status === "accepted" && (
        <div style={{ marginTop: 10 }}>
          {q.installments.map((e) => (
            <div key={e.id} style={{ display: "flex", gap: 10, alignItems: "center", padding: "5px 0" }}>
              <span className={`ball ${e.is_paid ? "you" : "done"}`}>{e.is_paid ? "Encaissée" : "À venir"}</span>
              <b>{fmtE(e.amount)}</b>
              <span className="hint">{fmtD(e.due_on)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export interface QuoteValues {
  amount_ht: string;
  parts: number;
  description: string;
}

export function QuoteForm({
  quote,
  onSave,
  onCancel,
  submitLabel = "Enregistrer et renvoyer",
}: {
  quote?: Partial<Quote>;
  onSave: (v: QuoteValues) => void;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const [v, setV] = useState<QuoteValues>({
    amount_ht: String(quote?.amount_ht ?? ""),
    parts: quote?.parts ?? 2,
    description: quote?.description ?? "",
  });
  return (
    <div className="qual">
      <div className="grid">
        <label className="field">
          Montant HT
          <input type="number" min={1} value={v.amount_ht} onChange={(e) => setV({ ...v, amount_ht: e.target.value })} />
        </label>
        <label className="field">
          Échéances
          <select value={v.parts} onChange={(e) => setV({ ...v, parts: Number(e.target.value) })}>
            <option value={1}>1 — à la commande</option>
            <option value={2}>2 — 50 % commande / 50 % livraison</option>
            <option value={3}>3 — 30 / 40 / 30</option>
          </select>
        </label>
      </div>
      <label className="field">
        Ce qui est proposé
        <textarea
          value={v.description}
          placeholder="Périmètre, livrables, délai…"
          onChange={(e) => setV({ ...v, description: e.target.value })}
        />
      </label>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        {onCancel && (
          <button className="btn ghost sm" onClick={onCancel}>
            Annuler
          </button>
        )}
        <button className="btn grad sm" disabled={!(Number(v.amount_ht) > 0)} onClick={() => onSave(v)}>
          {submitLabel}
        </button>
      </div>
    </div>
  );
}
