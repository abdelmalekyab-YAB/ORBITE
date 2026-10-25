/** Petits composants de la maquette : ball, tag, track, health, avatar, état vide. */
import { ReactNode } from "react";
import { ballOf, PRIORITY_LABEL, TYPE_LABEL, TYPE_TAG } from "../lib/format";
import type { Health, Ticket, UserMini } from "../lib/types";
import { useUI } from "./UIContext";

const AVATAR_COLORS = ["#7c3aed", "#0b8a9c", "#2b4cf2", "#a04bb5", "#c2410c", "#0f766e", "#be185d"];

export function Avatar({ user, small }: { user: UserMini | null | undefined; small?: boolean }) {
  if (!user)
    return (
      <span className={`av ${small ? "sm" : ""}`} style={{ background: "var(--s3)" }} title="Non assigné">
        ?
      </span>
    );
  return (
    <span
      className={`av ${small ? "sm" : ""}`}
      style={{ background: AVATAR_COLORS[user.id % AVATAR_COLORS.length] }}
      title={user.name}
    >
      {user.initials}
    </span>
  );
}

/** Pastille « À vous / Chez Digitalia / En retard ». `forDigitalia` : libellés côté équipe. */
export function BallBadge({ ticket, forDigitalia }: { ticket: Ticket; forDigitalia?: boolean }) {
  const b = ballOf(ticket);
  if (b === "done") return <span className="ball done">{forDigitalia ? ticket.status_label : ticket.client_label}</span>;
  if (b === "you") return <span className="ball you">{forDigitalia ? "Chez le client" : "À vous"}</span>;
  if (ticket.is_late) return <span className="ball late">En retard · Digitalia</span>;
  return <span className="ball dig">Chez Digitalia</span>;
}

export function TypeTag({ type }: { type: Ticket["type"] }) {
  return <span className={`tag ${TYPE_TAG[type]}`}>{TYPE_LABEL[type]}</span>;
}

export function Tags({ ticket }: { ticket: Ticket }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <TypeTag type={ticket.type} />
      {(ticket.priority === "high" || ticket.priority === "critical") && (
        <span className="tag" style={{ color: "var(--rose)" }}>
          {PRIORITY_LABEL[ticket.priority]}
        </span>
      )}
      {ticket.billing === "quote" && (
        <span className="tag" style={{ color: "var(--amber)" }}>
          Devis
        </span>
      )}
      {ticket.billing === "licence" && (
        <span className="tag" style={{ color: "var(--neon)" }}>
          Inclus licence
        </span>
      )}
      {ticket.is_internal && <span className="tag int">🔒 Interne</span>}
    </div>
  );
}

/**
 * Piste client (03-workflow) : étapes issues du workflow. « Proposition à valider » n'apparaît
 * que lorsque le ticket y est (docs/01 : 6 étapes + proposition quand un devis est en attente).
 */
export function Track({ ticket, labels }: { ticket: Ticket; labels?: boolean }) {
  const { workflow } = useUI();
  // Étapes issues du workflow enregistré en base (Réglages) ; rien tant qu'il n'est pas chargé.
  const all = workflow?.steps ?? [];
  if (!all.length) return null;
  const steps = all.filter((s) => s !== "Proposition à valider" || ticket.status === "devis");
  const delivered = ticket.client_label === steps[steps.length - 1];
  const idx = ticket.is_closed ? steps.length - 1 : Math.max(0, steps.indexOf(ticket.client_label));
  const cls = (i: number) => (delivered ? "ok" : i < idx ? "done" : i === idx ? "cur" : "");
  if (labels) {
    return (
      <div className="track lbl">
        {steps.map((s, i) => (
          <div key={s} className={cls(i)}>
            <i />
            {s}
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="track">
      {steps.map((s, i) => (
        <span key={s} className={cls(i)} title={s} />
      ))}
    </div>
  );
}

const HEALTH_LABEL: Record<Health, string> = { ok: "Tout avance", watch: "À surveiller", late: "En retard" };
export function HealthBadge({ health, style }: { health: Health; style?: React.CSSProperties }) {
  return (
    <span className={`health h-${health}`} style={style}>
      ● {HEALTH_LABEL[health]}
    </span>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <b>{title}</b>
      {children}
    </div>
  );
}

export function Loading() {
  return (
    <div className="empty">
      <b>Chargement…</b>
    </div>
  );
}
