import type { PayState } from "../api/types";
import { fmtDate } from "../lib/format";

/** Pastille de paiement (R15). Cliquable → ouvre le dialogue paiement. */
export function PayChip({
  state,
  due,
  paidOn,
  onClick,
}: {
  state: PayState;
  due?: string | null;
  paidOn?: string | null;
  onClick?: () => void;
}) {
  const txt =
    state === "paid"
      ? `Payé${paidOn ? " le " + fmtDate(paidOn, false) : ""}`
      : state === "late"
        ? `En retard${due ? " · éch. " + fmtDate(due, false) : ""}`
        : state === "due"
          ? `Échéance ${fmtDate(due, false)}`
          : "À encaisser";
  return (
    <button type="button" className={`fin-pay fin-pay--${state}`} onClick={onClick} title="Modifier le paiement">
      {txt}
    </button>
  );
}
