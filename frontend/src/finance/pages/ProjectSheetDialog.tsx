import { useRef, useState } from "react";
import { finance } from "../api/client";
import { DocViewer } from "../components/DocViewer";
import { PayChip } from "../components/PayChip";
import { eur, eur2, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";

/** Fiche projet (SPEC §5.8) : documents + stats + historique mois par mois. */
export function ProjectSheetDialog({ profileId, onClose }: { profileId: number; onClose: () => void }) {
  const { data, reload } = useApi(() => finance.sheet(profileId), [profileId]);
  const [doc, setDoc] = useState<{ url: string; name: string } | null>(null);
  const [kind, setKind] = useState("");
  const file = useRef<HTMLInputElement>(null);
  if (!data) return null;
  const p = data.profile;
  return (
    <dialog open className="fin-dialog fin-dialog--wide">
      <div className="fin-head">
        <div>
          <h2>
            {p.project_name}
            {p.status === "proposal" ? " · proposition non validée" : ""}
          </h2>
          <div className="fin-sub">
            {p.client_name} ·{" "}
            <span className={`fin-tag fin-tag--${p.billing_type}`}>
              {p.billing_type === "fixed"
                ? `${eur.format(n(p.monthly_amount))} / mois`
                : p.quote_amount
                  ? `Devis ${eur.format(n(p.quote_amount))}`
                  : "Sur devis"}
            </span>{" "}
            · depuis {monthLabel(data.first_billed_month)}
            {data.first_billed_month < p.start_month && p.billing_type === "fixed"
              ? ` (montant fixe depuis ${monthLabel(p.start_month)})`
              : ""}
            {p.end_month ? ` jusqu'à ${monthLabel(p.end_month)}` : ""}
          </div>
        </div>
        <button className="fin-btn fin-btn--ghost fin-btn--small" onClick={onClose}>
          Fermer
        </button>
      </div>
      <div className="fin-stats">
        <div className="fin-stat">
          <b className="fin-num">{eur.format(n(data.billed))}</b>
          <span>Total facturé</span>
        </div>
        <div className="fin-stat">
          <b className="fin-num">{data.remaining == null ? "—" : eur.format(n(data.remaining))}</b>
          <span>Reste à facturer</span>
        </div>
        <div className="fin-stat">
          <b className="fin-num">{eur.format(n(data.planned))}</b>
          <span>Factures planifiées</span>
        </div>
        <div className="fin-stat">
          <b className="fin-num">{data.margin == null ? "—" : eur.format(n(data.margin))}</b>
          <span>{n(data.cost) ? `Marge (coût ${eur.format(n(data.cost))})` : "Marge (pas de coût saisi)"}</span>
        </div>
      </div>
      <div className="fin-docs">
        {p.note && <p className="fin-sub">{p.note}</p>}
        <b>Documents du projet</b>
        {p.documents.length ? (
          p.documents.map((d) => (
            <div className="fin-entry" key={d.id}>
              <span>
                {d.kind && <span className="fin-tag">{d.kind}</span>}{" "}
                <button className="fin-clip" onClick={() => setDoc({ url: d.url, name: d.name })}>
                  📎 {d.name}
                </button>
              </span>
            </div>
          ))
        ) : (
          <div className="fin-sub">Aucun document joint.</div>
        )}
        <div className="fin-inline">
          <input
            placeholder="Type (devis, proposition, bon de commande…)"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          />
          <button className="fin-btn fin-btn--small" onClick={() => file.current?.click()}>
            Joindre un document
          </button>
          <input
            ref={file}
            type="file"
            hidden
            accept=".pdf,image/*"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (f) {
                await finance.addProjectDocument(profileId, f, kind);
                setKind("");
                reload();
              }
            }}
          />
        </div>
      </div>
      <table className="fin-table">
        <thead>
          <tr>
            <th>Mois</th>
            <th>Détail</th>
            <th className="r">Montant</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.month}>
              <td style={{ whiteSpace: "nowrap" }}>
                <b style={{ textTransform: "capitalize" }}>{monthLabel(r.month)}</b>
                {r.to_bill ? (
                  <div className="fin-sub fin-warn">À facturer</div>
                ) : r.future ? (
                  <div className="fin-sub">Prévu</div>
                ) : null}
              </td>
              <td>
                {n(r.fixed) > 0 && (
                  <div className="fin-entry">
                    <span>Montant fixe</span>
                    <span className="fin-num">{eur2.format(n(r.fixed))}</span>
                  </div>
                )}
                {r.invoices.map((i) => (
                  <div className="fin-entry" key={i.id}>
                    <span>
                      {i.pending && (
                        <span className="fin-tag fin-tag--quote">{r.month <= data.rows[0].month ? "À facturer" : "Prévue"}</span>
                      )}
                      {i.kind === "deposit" && <span className="fin-tag fin-tag--fixed">Démarrage</span>} {i.label || "Facture"}
                    </span>
                    <span className="fin-num">
                      {i.pay_state && <PayChip state={i.pay_state} />} {eur2.format(n(i.amount))}
                    </span>
                  </div>
                ))}
              </td>
              <td className="r fin-num">
                <b>{eur2.format(n(r.total))}</b>
              </td>
            </tr>
          ))}
          <tr className="fin-total">
            <td colSpan={2}>Total facturé à ce jour</td>
            <td className="r fin-num">{eur2.format(n(data.billed))}</td>
          </tr>
        </tbody>
      </table>
      {doc && <DocViewer url={doc.url} name={doc.name} onClose={() => setDoc(null)} />}
    </dialog>
  );
}
