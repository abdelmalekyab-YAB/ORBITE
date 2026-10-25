/** Confirmation intégrée (jamais window.confirm : bloqué dans certains contextes). */
export function ConfirmInline({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fin-confirm" role="alert">
      <div>{message}</div>
      <div className="fin-row fin-row--end">
        <button type="button" className="fin-btn fin-btn--ghost fin-btn--small" onClick={onCancel}>
          Annuler
        </button>
        <button type="button" className="fin-btn fin-btn--danger fin-btn--small" onClick={onConfirm}>
          Oui, supprimer
        </button>
      </div>
    </div>
  );
}
