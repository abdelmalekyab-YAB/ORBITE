import { useState } from "react";
import type { PaymentStatus, PaymentUpdate } from "../api/types";

interface Props {
  title: string;
  hint?: string;
  initial: { payment_status: PaymentStatus; due_date: string | null; paid_on: string | null };
  onSave: (data: PaymentUpdate) => Promise<void>;
  onClose: () => void;
}

/** Dialogue « paiement » : statut, échéance, payé le (SPEC §6). */
export function PaymentDialog({ title, hint, initial, onSave, onClose }: Props) {
  const [status, setStatus] = useState<PaymentStatus>(initial.payment_status);
  const [due, setDue] = useState(initial.due_date ?? "");
  const [paidOn, setPaidOn] = useState(initial.paid_on ?? "");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await onSave({
        payment_status: status,
        due_date: due || null,
        paid_on: status === "paid" ? paidOn || new Date().toISOString().slice(0, 10) : null,
      });
      onClose();
    } finally {
      setBusy(false);
    }
  };
  return (
    <dialog open className="fin-dialog" aria-labelledby="pay-title">
      <h2 id="pay-title">{title}</h2>
      {hint && <p className="fin-sub">{hint}</p>}
      <div className="fin-row">
        <label>
          Statut
          <select value={status} onChange={(e) => setStatus(e.target.value as PaymentStatus)}>
            <option value="pending">En attente de paiement</option>
            <option value="late">En retard</option>
            <option value="paid">Payé</option>
          </select>
        </label>
        <label>
          Date d'échéance
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
      </div>
      {status === "paid" && (
        <label>
          Payé le
          <input type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />
        </label>
      )}
      <div className="fin-row fin-row--end">
        <button type="button" className="fin-btn fin-btn--ghost" onClick={onClose}>
          Annuler
        </button>
        <button type="button" className="fin-btn" disabled={busy} onClick={submit}>
          Enregistrer
        </button>
      </div>
    </dialog>
  );
}
