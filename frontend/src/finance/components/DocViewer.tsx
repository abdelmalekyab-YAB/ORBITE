/**
 * Visionneuse de documents dans l'application (SPEC §5.9).
 * Les fichiers étant servis en same-origin par Django (MEDIA_URL), un <iframe> suffit.
 * Si Orbit sert les médias depuis un autre domaine, passer par pdf.js (comme la plateforme actuelle).
 */
export function DocViewer({ url, name, onClose }: { url: string; name: string; onClose: () => void }) {
  const isImg = /\.(png|jpe?g|webp|gif)$/i.test(name);
  return (
    <dialog open className="fin-dialog fin-dialog--wide">
      <div className="fin-head">
        <h2 style={{ wordBreak: "break-all" }}>{name}</h2>
        <div className="fin-row">
          <a className="fin-btn fin-btn--small" href={url} download={name}>
            Télécharger
          </a>
          <button type="button" className="fin-btn fin-btn--ghost fin-btn--small" onClick={onClose}>
            Fermer
          </button>
        </div>
      </div>
      {isImg ? (
        <img src={url} alt="" style={{ maxWidth: "100%" }} />
      ) : (
        <iframe title={name} src={url} style={{ width: "100%", height: "72vh", border: 0 }} />
      )}
    </dialog>
  );
}
