import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AttachmentList } from "../../components/Attachments";
import { Empty, Loading, TypeTag } from "../../components/bits";
import { useUI } from "../../components/UIContext";
import { ApiError, formData, post } from "../../lib/api";
import { fmtD, fmtE, PRIORITY_LABEL, TYPE_LABEL } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import type { Milestone, Priority, Ticket, TicketDetail, TicketType } from "../../lib/types";

type Decision = "faire" | "analyser" | "attente" | "refuse" | "devis";

/** Triage (pm/admin) : qualifier et décider (règles 13-14). */
export default function Triage({ members }: { members: { id: number; name: string }[] }) {
  const queue = useApi<Ticket[]>("/triage");
  const [params, setParams] = useSearchParams();
  const wanted = Number(params.get("t")) || null;
  const list = queue.data ?? [];
  const selected = wanted ?? list[0]?.id ?? null;

  return (
    <>
      <h1 style={{ marginBottom: 4 }}>Triage</h1>
      <p className="hint" style={{ marginBottom: 18 }}>
        Les demandes reçues, à qualifier et planifier. Le client est prévenu dès qu'une décision est prise.
      </p>
      {!queue.data ? (
        <Loading />
      ) : (
        <div className="triage">
          <div className="tq">
            {list.length ? (
              list.map((x) => (
                <div
                  key={x.id}
                  role="button"
                  tabIndex={0}
                  className={`it ${x.id === selected ? "on" : ""}`}
                  onClick={() => setParams({ t: String(x.id) })}
                  onKeyDown={(e) => e.key === "Enter" && setParams({ t: String(x.id) })}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <TypeTag type={x.type} />
                    <span className="hint">{fmtD(x.created_at)}</span>
                  </div>
                  <b>{x.title}</b>
                  <span>
                    {x.project_name} · {x.author.name}
                    {x.status === "analyser" ? " · en analyse" : ""}
                  </span>
                </div>
              ))
            ) : (
              <div className="card">
                <Empty title="File vide">Aucune demande à qualifier.</Empty>
              </div>
            )}
          </div>
          {selected && (
            <Qualify
              key={selected}
              id={selected}
              members={members}
              onDone={() => {
                setParams({});
                queue.reload();
              }}
            />
          )}
        </div>
      )}
    </>
  );
}

function Qualify({ id, members, onDone }: { id: number; members: { id: number; name: string }[]; onDone: () => void }) {
  const { toast, bump } = useUI();
  const { data: t } = useApi<TicketDetail>(`/tickets/${id}`);
  const milestones = useApi<Milestone[]>(t ? `/projects/${t.project}/milestones` : null);
  const settings = useApi<{ default_tjm: string }>("/finance/settings");
  const tjm = Number(settings.data?.default_tjm ?? 0); // 0 = TJM non défini dans Finances
  const [f, setF] = useState({
    type: "" as TicketType | "",
    priority: "normal" as Priority,
    assignee: "",
    milestone: "",
    due_on: "",
    estimate_days: "",
    billing: "licence" as "licence" | "quote",
    message: "",
    amount: "",
    parts: 2,
    description: "",
  });
  const [pdf, setPdf] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!t) return;
    setF((x) => ({
      ...x,
      type: t.type,
      priority: t.priority,
      assignee: t.assignee ? String(t.assignee.id) : "",
      milestone: t.milestone ? String(t.milestone.id) : "",
      due_on: t.due_on ?? "",
      estimate_days: t.estimate_days ?? "",
      billing: t.billing === "quote" ? "quote" : "licence",
      amount: t.quote_detail?.amount_ht ?? "",
      parts: t.quote_detail?.parts ?? 2,
      description: t.quote_detail?.description ?? "",
    }));
  }, [t]);

  if (!t)
    return (
      <div className="card">
        <Loading />
      </div>
    );
  const billable = f.type === "evolution" || f.type === "feature";
  const quoteMode = billable && f.billing === "quote";
  const suggested = Math.round(Number(f.estimate_days || 0) * tjm);
  const set = (patch: Partial<typeof f>) => setF((x) => ({ ...x, ...patch }));

  async function decide(decision: Decision) {
    setBusy(true);
    try {
      await post(`/tickets/${t!.id}/triage`, withPdf(decision));
      toast(
        {
          faire: "Demande planifiée",
          analyser: "Gardée en analyse",
          attente: "Précision demandée au client",
          refuse: "Demande refusée",
          devis: "Proposition envoyée au client",
        }[decision],
      );
      bump();
      onDone();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Décision impossible");
    } finally {
      setBusy(false);
    }
  }

  function withPdf(decision: Decision) {
    const fd = formData({
      decision,
      type: f.type,
      priority: f.priority,
      assignee: f.assignee,
      milestone: f.milestone,
      due_on: f.due_on,
      estimate_days: f.estimate_days,
      billing: billable ? f.billing : undefined,
      message: f.message,
      ...(decision === "devis"
        ? { quote_amount_ht: f.amount || suggested, quote_parts: f.parts, quote_description: f.description }
        : {}),
    });
    if (decision === "devis" && pdf) fd.append("quote_pdf", pdf, pdf.name);
    return fd;
  }

  return (
    <div className="card qual" data-testid="qualify">
      <div>
        <div className="hint">
          {t.ref} · {t.project_name} · déposée par {t.author.name} le {fmtD(t.created_at)}
        </div>
        <h2 style={{ margin: "4px 0 8px", fontSize: 20 }}>{t.title}</h2>
        <div className="desc">{t.description || <span className="hint">Pas de description.</span>}</div>
        <AttachmentList items={t.attachments} />
      </div>
      <div className="grid">
        <label className="field">
          Type
          <select value={f.type} onChange={(e) => set({ type: e.target.value as TicketType })}>
            {(Object.keys(TYPE_LABEL) as TicketType[]).map((k) => (
              <option key={k} value={k}>
                {TYPE_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Priorité
          <select value={f.priority} onChange={(e) => set({ priority: e.target.value as Priority })}>
            {Object.entries(PRIORITY_LABEL).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Responsable
          <select value={f.assignee} onChange={(e) => set({ assignee: e.target.value })}>
            <option value="">Non assigné</option>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Version
          <select value={f.milestone} onChange={(e) => set({ milestone: e.target.value })}>
            <option value="">Pas encore</option>
            {milestones.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Date cible
          <input type="date" value={f.due_on} onChange={(e) => set({ due_on: e.target.value })} />
        </label>
        <label className="field">
          Estimation (jours)
          <input
            type="number"
            step="0.5"
            min={0}
            value={f.estimate_days}
            onChange={(e) => set({ estimate_days: e.target.value })}
          />
        </label>
      </div>
      {billable && (
        <div className="field">
          Facturation
          <div className="impact" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <button type="button" className={f.billing === "licence" ? "on" : ""} onClick={() => set({ billing: "licence" })}>
              <b>Inclus dans la licence</b>
              <span>Couvert par l'abonnement</span>
            </button>
            <button type="button" className={f.billing === "quote" ? "on" : ""} onClick={() => set({ billing: "quote" })}>
              <b>Sur devis</b>
              <span>Proposition commerciale à valider</span>
            </button>
          </div>
        </div>
      )}
      {quoteMode && (
        <div className="card tight" style={{ borderColor: "rgba(255,193,77,.4)" }}>
          <h3 style={{ marginBottom: 8, color: "var(--amber)" }}>Proposition commerciale</h3>
          <div className="grid">
            <label className="field">
              Montant HT
              <input
                type="number"
                min={1}
                value={f.amount}
                placeholder={String(suggested || "")}
                onChange={(e) => set({ amount: e.target.value })}
              />
            </label>
            <label className="field">
              Échéances
              <select value={f.parts} onChange={(e) => set({ parts: Number(e.target.value) })}>
                <option value={1}>1 — à la commande</option>
                <option value={2}>2 — 50 % commande / 50 % livraison</option>
                <option value={3}>3 — 30 / 40 / 30</option>
              </select>
            </label>
          </div>
          <label className="field" style={{ marginTop: 10 }}>
            Ce qui est proposé
            <textarea
              value={f.description}
              placeholder="Périmètre, livrables, délai…"
              onChange={(e) => set({ description: e.target.value })}
            />
          </label>
          <div className="att-bar" style={{ marginTop: 8 }}>
            <label>
              📎 {pdf ? pdf.name : "Joindre le PDF du devis"}
              <input type="file" accept="application/pdf" onChange={(e) => setPdf(e.target.files?.[0] ?? null)} />
            </label>
          </div>
          <p className="hint" style={{ marginTop: 6 }}>
            {suggested ? `Aide au chiffrage : ${f.estimate_days} j × ${fmtE(tjm)} = ${fmtE(suggested)}. ` : ""}
            {!tjm && "TJM de référence non défini (onglet Finances) : saisissez le montant. "}
            Le client la voit dans son espace et l'accepte ou la refuse ; le développement ne démarre qu'après son accord.
          </p>
        </div>
      )}
      <label className="field">
        Message au client (optionnel)
        <textarea
          value={f.message}
          placeholder="Ex. : Merci, c'est planifié dans la version 2.4."
          onChange={(e) => set({ message: e.target.value })}
        />
      </label>
      <div className="acts">
        <button className="btn rose" disabled={busy} onClick={() => decide("refuse")}>
          Refuser
        </button>
        <button className="btn" disabled={busy} onClick={() => decide("attente")}>
          Demander une précision
        </button>
        <button className="btn" disabled={busy || t.status === "analyser"} onClick={() => decide("analyser")}>
          Garder en analyse
        </button>
        {quoteMode ? (
          <button className="btn grad" disabled={busy || !(Number(f.amount || suggested) > 0)} onClick={() => decide("devis")}>
            ✓ Envoyer la proposition
          </button>
        ) : (
          <button className="btn grad" disabled={busy} onClick={() => decide("faire")}>
            ✓ Planifier
          </button>
        )}
      </div>
    </div>
  );
}
