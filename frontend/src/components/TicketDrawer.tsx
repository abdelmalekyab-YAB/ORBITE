import { ReactNode, useEffect, useState } from "react";
import { useMe } from "../auth/AuthContext";
import { ApiError, formData, patch, post } from "../lib/api";
import { fmtD, fmtDT, PRIORITY_LABEL, stepLabel } from "../lib/format";
import { useApi } from "../lib/hooks";
import type { Comment, Milestone, Priority, TicketDetail, TicketEvent } from "../lib/types";
import { AttachmentList, AttBar, PendingList, useAttachments } from "./Attachments";
import { useNavigate } from "react-router-dom";
import { Avatar, BallBadge, Tags, Track } from "./bits";
import QuoteCard from "./QuoteCard";
import { useUI } from "./UIContext";

type Refusal = "testko" | "reopen" | "qrefuse";
const REFUSAL_TEXT: Record<Refusal, { h: string; p: string; btn: string }> = {
  testko: {
    h: "Ce test n'est pas concluant — expliquez ce qui cloche",
    p: "Un texte, une photo, une vidéo ou un message vocal : l'équipe corrige sans deviner.",
    btn: "Envoyer mon refus",
  },
  reopen: {
    h: "Rouvrir cette demande — que se passe-t-il ?",
    p: "Décrivez le problème rencontré après la livraison.",
    btn: "Rouvrir la demande",
  },
  qrefuse: {
    h: "Refuser la proposition — pour quelle raison ?",
    p: "Trop cher, hors périmètre, pas maintenant… ça aide Digitalia à ajuster.",
    btn: "Refuser la proposition",
  },
};
const MIN_REASON = 10;

interface TeamMember {
  user: { id: number; name: string };
}

export default function TicketDrawer() {
  const { ticketId, openTicket } = useUI();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && openTicket(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openTicket]);
  return (
    <>
      <div className={`ov ${ticketId ? "show" : ""}`} onClick={() => openTicket(null)} />
      <aside className={`drawer ${ticketId ? "show" : ""}`} aria-hidden={!ticketId}>
        {ticketId && <DrawerBody key={ticketId} id={ticketId} />}
      </aside>
    </>
  );
}

function DrawerBody({ id }: { id: number }) {
  const me = useMe();
  const dig = me.is_digitalia;
  const { openTicket, toast, bump, drawerIntent } = useUI();
  const { data: t, setData, error } = useApi<TicketDetail>(`/tickets/${id}`);
  const events = useApi<TicketEvent[]>(`/tickets/${id}/events`);
  const [refusal, setRefusal] = useState<Refusal | null>(drawerIntent);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (error)
    return (
      <div className="db">
        <p className="hint">{error}</p>
      </div>
    );
  if (!t)
    return (
      <div className="db">
        <p className="hint">Chargement…</p>
      </div>
    );

  /** Exécute une mutation qui renvoie le ticket à jour. */
  async function run(action: () => Promise<TicketDetail>, done?: string) {
    setBusy(true);
    try {
      setData(await action());
      events.reload();
      bump();
      if (done) toast(done);
      return true;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Une erreur est survenue");
      return false;
    } finally {
      setBusy(false);
    }
  }
  const move = (to: string, msg: string, comment?: string, files: File[] = []) =>
    run(() => post<TicketDetail>(`/tickets/${t.id}/transition`, formData({ to, comment }, files)), msg);

  const canTriage = dig && (me.job === "pm" || me.job === "admin");
  const toTriage = () => {
    openTicket(null);
    navigate(`/dig/triage?t=${t.id}`);
  };
  const banner = refusal
    ? null
    : dig
      ? digitaliaBanner(t, move, run, canTriage ? toTriage : null)
      : clientBanner(t, move, setRefusal);

  return (
    <>
      <div className="dh">
        <button className="btn ghost sm" onClick={() => openTicket(null)} aria-label="Fermer">
          ✕
        </button>
        <span className="hint">
          {t.ref} · {t.project_name}
          {t.parent && (
            <>
              {" "}
              · sous-tâche de <a onClick={() => openTicket(t.parent!.id)}>{t.parent.ref}</a>
            </>
          )}
        </span>
        <span style={{ marginLeft: "auto" }}>
          <BallBadge ticket={t} forDigitalia={dig} />
        </span>
      </div>
      <div className="db">
        <div>
          <div style={{ marginBottom: 8 }}>
            <Tags ticket={t} />
          </div>
          <h1>{t.title}</h1>
          {!t.is_internal && <Track ticket={t} labels />}
          <div className="step-now" style={{ marginTop: 6 }}>
            {dig ? t.status_label : stepLabel(t)}
          </div>
        </div>

        {refusal && (
          <RefusalBlock
            kind={refusal}
            busy={busy}
            onCancel={() => setRefusal(null)}
            onSend={async (text, files) => {
              const ok =
                refusal === "qrefuse"
                  ? await run(
                      () => post<TicketDetail>(`/tickets/${t.id}/quote/refuse`, formData({ reason: text }, files)),
                      "Proposition refusée — Digitalia est prévenu",
                    )
                  : await move("cours", refusal === "testko" ? "Refus envoyé à Digitalia" : "Demande rouverte", text, files);
              if (ok) setRefusal(null);
              return ok;
            }}
          />
        )}
        {banner}
        {!refusal && <QuoteCard t={t} run={run} onRefuse={() => setRefusal("qrefuse")} />}

        <div className="card tight">
          <h3 style={{ marginBottom: 8 }}>Description</h3>
          <div className="desc">{t.description || <span className="hint">Pas de description.</span>}</div>
          <AttachmentList items={t.attachments} />
        </div>

        {dig && t.children.length > 0 && (
          <div className="card tight">
            <h3 style={{ marginBottom: 8 }}>Sous-tâches</h3>
            <div className="todo">
              {t.children.map((c) => (
                <div className="ti" key={c.id} onClick={() => openTicket(c.id)}>
                  <span className="why" style={{ background: "var(--s3)", color: "var(--ink2)" }}>
                    {c.status_label}
                  </span>
                  <div className="t">{c.title}</div>
                  <span className="hint">{c.ref}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <Discussion
          t={t}
          busy={busy}
          onSend={(body, files) =>
            run(() => post<TicketDetail>(`/tickets/${t.id}/comments`, formData({ body }, files)), "Message envoyé")
          }
        />

        <Informations
          t={t}
          onChange={(field, value) => run(() => patch<TicketDetail>(`/tickets/${t.id}`, { [field]: value }), "Enregistré")}
          onMove={(to) => move(to, "Statut mis à jour")}
        />

        <div className="card tight">
          <h3 style={{ marginBottom: 8 }}>Historique</h3>
          <div className="hist">
            {[...(events.data ?? [])].reverse().map((e) => (
              <div key={e.id}>
                {fmtDT(e.at)} · <b>{e.actor?.name ?? "Orbit"}</b> {eventText(e)}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

type Move = (to: string, msg: string, comment?: string, files?: File[]) => Promise<boolean>;

function clientBanner(t: TicketDetail, move: Move, refuse: (k: Refusal) => void): ReactNode {
  switch (t.status) {
    case "test":
      return (
        <div className="banner b-you">
          🧪 Prêt à tester. Dites-nous si c'est bon.
          <div className="bt">
            <button className="btn neon sm" onClick={() => move("termine", "Merci ! Demande livrée")}>
              ✓ C'est bon
            </button>
            <button className="btn rose sm" onClick={() => refuse("testko")}>
              ✕ Pas OK
            </button>
          </div>
        </div>
      );
    case "attente":
      return <div className="banner b-q">💬 Digitalia attend votre réponse. Répondez dans la discussion ci-dessous.</div>;
    case "termine":
      return (
        <div className="banner b-ok">
          ✅ Livrée. Un souci après coup ?
          <div className="bt">
            <button className="btn sm" onClick={() => refuse("reopen")}>
              Rouvrir
            </button>
          </div>
        </div>
      );
    case "nouveau":
      return <div className="banner b-dig">Reçue. Digitalia la qualifie sous 48 h et vous prévient.</div>;
    case "devis":
      return (
        <div className="banner b-q">📄 Une proposition commerciale vous attend. Le développement démarre dès votre accord.</div>
      );
    case "testint":
      return (
        <div className="banner b-dig">
          🔎 En validation interne chez Digitalia — vous le recevrez à tester dès que c'est vérifié.
        </div>
      );
    default:
      if (t.is_closed) return <div className="banner b-ok">{t.client_label}.</div>;
      return (
        <div className="banner b-dig">
          Chez Digitalia — {stepLabel(t)}
          {t.due_on ? `, livraison prévue le ${fmtD(t.due_on)}` : ""}.
        </div>
      );
  }
}

function digitaliaBanner(
  t: TicketDetail,
  move: Move,
  run: (a: () => Promise<TicketDetail>, done?: string) => Promise<boolean>,
  toTriage: (() => void) | null,
): ReactNode {
  const btn = (to: string, label: string, cls: string, msg: string) =>
    t.allowed_transitions.includes(to) && (
      <button className={`btn ${cls} sm`} onClick={() => move(to, msg)}>
        {label}
      </button>
    );
  const ping = () => run(() => post<TicketDetail>(`/tickets/${t.id}/ping`, {}), "Client relancé");
  switch (t.status) {
    case "nouveau":
    case "analyser":
      return (
        <div className="banner b-dig">
          À qualifier{toTriage ? "." : " par un chef de projet."}
          {toTriage && (
            <div className="bt">
              <button className="btn sm" onClick={toTriage}>
                Ouvrir dans le triage
              </button>
            </div>
          )}
        </div>
      );
    case "cours":
      return (
        <div className="banner b-dig">
          En développement. Livré en préprod ?
          <div className="bt">
            {btn("testint", "Passer en test interne", "grad", "Passé en test interne")}
            {btn("attente", "Demander une précision", "", "Précision demandée au client")}
          </div>
        </div>
      );
    case "testint":
      return (
        <div className="banner b-dig">
          🔎 Test interne — à valider par l'équipe avant envoi au client.
          <div className="bt">
            {btn("test", "✓ Validé, envoyer au client", "neon", "Envoyé au client pour test")}
            {btn("cours", "Retour en dev", "rose", "Retour en développement")}
          </div>
        </div>
      );
    case "faire":
      return (
        <div className="banner b-dig">
          Planifiée{t.milestone ? ` · ${t.milestone.name}` : ""}.
          <div className="bt">{btn("cours", "Démarrer", "grad", "Développement démarré")}</div>
        </div>
      );
    case "devis":
      return <div className="banner b-you">📄 Proposition envoyée, en attente de la décision du client.</div>;
    case "attente":
    case "test":
      return (
        <div className="banner b-you">
          Chez le client depuis le {fmtD(t.updated_at)}.
          <div className="bt">
            {!t.is_internal && (
              <button className="btn sm" onClick={ping}>
                Relancer
              </button>
            )}
            {btn("cours", "Reprendre", "", "Repris en développement")}
          </div>
        </div>
      );
    case "termine":
      return <div className="banner b-ok">✅ Livrée le {fmtD(t.closed_at)}.</div>;
    default:
      return null;
  }
}

function RefusalBlock({
  kind,
  busy,
  onCancel,
  onSend,
}: {
  kind: Refusal;
  busy: boolean;
  onCancel: () => void;
  onSend: (text: string, files: File[]) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState(false);
  const att = useAttachments();
  const txt = REFUSAL_TEXT[kind];
  // Règle 10, vérifiée aussi côté API : ≥ 10 caractères ou une pièce jointe audio/vidéo.
  const valid = text.trim().length >= MIN_REASON || att.files.some((f) => /^(audio|video)\//.test(f.type));

  async function send() {
    if (!valid) return setError(true);
    if (await onSend(text, att.files)) att.clear();
  }
  return (
    <div className="refus">
      <h3>{txt.h}</h3>
      <p className="hint" style={{ marginBottom: 10 }}>
        {txt.p}
      </p>
      <div className="compose">
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setError(false);
          }}
          style={{ minHeight: 100 }}
          aria-label="Motif"
          placeholder="Décrivez le problème : sur quelle page, ce que vous attendiez, ce qui s'est passé…"
        />
        <AttBar state={att} />
        <PendingList state={att} />
        {error && (
          <div className="hint" style={{ color: "var(--rose)" }}>
            Il faut une explication écrite (10 caractères minimum), vocale ou vidéo pour envoyer.
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 6 }}>
          <button className="btn ghost" onClick={onCancel}>
            Annuler
          </button>
          <button className="btn rose" disabled={busy} onClick={send}>
            {txt.btn}
          </button>
        </div>
      </div>
    </div>
  );
}

const KIND_LABEL: Partial<Record<Comment["kind"], string>> = {
  refusal: "Test refusé",
  reopen: "Demande rouverte",
  quote_refusal: "Proposition refusée",
  ping: "Relance",
};

function Discussion({
  t,
  busy,
  onSend,
}: {
  t: TicketDetail;
  busy: boolean;
  onSend: (body: string, files: File[]) => Promise<boolean>;
}) {
  const me = useMe();
  const [body, setBody] = useState("");
  const att = useAttachments();
  async function send() {
    if (!body.trim() && !att.files.length) return;
    if (await onSend(body, att.files)) {
      setBody("");
      att.clear();
    }
  }
  return (
    <div className="card tight">
      <h3 style={{ marginBottom: 10 }}>Discussion</h3>
      {t.comments.length ? (
        t.comments.map((c) => {
          const refusal = c.kind === "refusal" || c.kind === "reopen" || c.kind === "quote_refusal";
          return (
            <div key={c.id} className={`msg ${c.author.id === me.id ? "me" : ""}`}>
              <Avatar user={c.author} />
              <div
                className="b"
                style={refusal ? { background: "var(--rsoft)", border: "1px solid rgba(255,107,138,.4)" } : undefined}
              >
                <div className="h">
                  <b>{c.author.name}</b> · {c.author_is_digitalia ? "Digitalia" : "Client"} · {fmtDT(c.created_at)}
                  {KIND_LABEL[c.kind] && (
                    <span className="tag" style={{ marginLeft: 6, color: refusal ? "var(--rose)" : undefined }}>
                      {KIND_LABEL[c.kind]}
                    </span>
                  )}
                </div>
                <div className="desc">{c.body}</div>
                <AttachmentList items={c.attachments} />
              </div>
            </div>
          );
        })
      ) : (
        <p className="hint" style={{ marginBottom: 10 }}>
          Pas encore de message.
        </p>
      )}
      <div className="compose">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          aria-label="Message"
          placeholder={me.is_digitalia ? "Écrire au client ou à l'équipe…" : "Écrire à Digitalia…"}
        />
        <AttBar state={att} />
        <PendingList state={att} />
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button className="btn grad sm" disabled={busy} onClick={send}>
            Envoyer
          </button>
        </div>
      </div>
    </div>
  );
}

function Informations({
  t,
  onChange,
  onMove,
}: {
  t: TicketDetail;
  onChange: (field: string, value: unknown) => void;
  onMove: (to: string) => void;
}) {
  const me = useMe();
  const { workflow } = useUI();
  const dig = me.is_digitalia;
  const team = useApi<{ members: TeamMember[] }>(dig ? "/team" : null);
  const milestones = useApi<Milestone[]>(dig ? `/projects/${t.project}/milestones` : null);
  const label = (key: string) => workflow?.statuses.find((s) => s.key === key)?.label ?? key;

  if (!dig) {
    return (
      <div className="card tight">
        <h3 style={{ marginBottom: 10 }}>Informations</h3>
        <div className="kv">
          <span>Déposée par</span>
          <span>
            {t.author.name} · {fmtDT(t.created_at)}
          </span>
          <span>Responsable</span>
          <span>{t.assignee?.name ?? "Pas encore attribué"}</span>
          <span>Étape</span>
          <span>{t.client_label}</span>
          <span>Priorité</span>
          <span>{PRIORITY_LABEL[t.priority]}</span>
          <span>Version</span>
          <span>{t.milestone?.name ?? "Pas encore planifiée"}</span>
          <span>Date prévue</span>
          <span className={t.is_late ? "late" : ""}>{fmtD(t.due_on)}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="card tight">
      <h3 style={{ marginBottom: 10 }}>Informations</h3>
      <div className="kv">
        <span>Déposée par</span>
        <span>
          {t.author.name} · {fmtDT(t.created_at)}
        </span>
        <span>Responsable</span>
        <span>
          <select
            aria-label="Responsable"
            value={t.assignee?.id ?? ""}
            onChange={(e) => onChange("assignee", e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Non assigné</option>
            {team.data?.members.map((m) => (
              <option key={m.user.id} value={m.user.id}>
                {m.user.name}
              </option>
            ))}
          </select>
        </span>
        <span>Statut</span>
        <span>
          <select aria-label="Statut" value={t.status} onChange={(e) => onMove(e.target.value)}>
            <option value={t.status}>{t.status_label}</option>
            {t.allowed_transitions.map((k) => (
              <option key={k} value={k}>
                → {label(k)}
              </option>
            ))}
          </select>
        </span>
        <span>Priorité</span>
        <span>
          <select aria-label="Priorité" value={t.priority} onChange={(e) => onChange("priority", e.target.value as Priority)}>
            {Object.entries(PRIORITY_LABEL).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </span>
        <span>Version</span>
        <span>
          <select
            aria-label="Version"
            value={t.milestone?.id ?? ""}
            onChange={(e) => onChange("milestone", e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">—</option>
            {milestones.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </span>
        <span>Date prévue</span>
        <span>
          <input
            type="date"
            aria-label="Date prévue"
            value={t.due_on ?? ""}
            onChange={(e) => onChange("due_on", e.target.value || null)}
          />
        </span>
        <span>Visibilité</span>
        <span>
          <select
            aria-label="Visibilité"
            value={t.is_internal ? "0" : "1"}
            onChange={(e) => onChange("is_internal", e.target.value === "0")}
          >
            <option value="1">Visible par le client</option>
            <option value="0">Interne Digitalia</option>
          </select>
        </span>
      </div>
    </div>
  );
}

function eventText(e: TicketEvent): string {
  switch (e.kind) {
    case "created":
      return "a créé la demande";
    case "status":
      return `a modifié le statut : ${e.message}`;
    case "comment":
      return e.to_value === "refusal"
        ? "a refusé le test"
        : e.to_value === "reopen"
          ? "a rouvert la demande"
          : "a écrit un message";
    case "assignee":
      return "a changé le responsable";
    case "ping":
      return "a relancé le client";
    case "field":
      return `a modifié ${FIELD_LABEL[e.message] ?? e.message}`;
    default:
      return e.message || e.kind;
  }
}
const FIELD_LABEL: Record<string, string> = {
  title: "le titre",
  description: "la description",
  type: "le type",
  priority: "la priorité",
  milestone: "la version",
  due_on: "la date prévue",
  is_internal: "la visibilité",
  billing: "la facturation",
  estimate_days: "l'estimation",
};
