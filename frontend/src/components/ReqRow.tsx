import { fmtD, stepLabel } from "../lib/format";
import type { Ticket } from "../lib/types";
import { Avatar, BallBadge, Tags, Track } from "./bits";
import { useUI } from "./UIContext";

/** Ligne de demande avec piste (composant `req` de la maquette). */
export default function ReqRow({
  ticket: t,
  forDigitalia,
  showProject,
}: {
  ticket: Ticket;
  forDigitalia?: boolean;
  showProject?: boolean;
}) {
  const { openTicket } = useUI();
  const when = t.due_on ? `prévu le ${fmtD(t.due_on)}` : t.milestone ? t.milestone.name : "pas encore planifié";
  return (
    <div
      className="req"
      role="button"
      tabIndex={0}
      onClick={() => openTicket(t.id)}
      onKeyDown={(e) => e.key === "Enter" && openTicket(t.id)}
    >
      <div>
        <Tags ticket={t} />
        <div className="t">{t.title}</div>
        <div className="meta">
          <span className="ref">{t.ref}</span>
          {showProject && (
            <span className="tag" style={{ color: "var(--violet)" }}>
              {t.project_name}
            </span>
          )}
          <span className="step-now">{forDigitalia ? t.status_label : stepLabel(t)}</span>
        </div>
        {!t.is_internal && <Track ticket={t} />}
      </div>
      <div className="right">
        <BallBadge ticket={t} forDigitalia={forDigitalia} />
        <span className={`hint ${t.is_late ? "late" : ""}`}>{when}</span>
        {forDigitalia && <Avatar user={t.assignee} small />}
      </div>
    </div>
  );
}
