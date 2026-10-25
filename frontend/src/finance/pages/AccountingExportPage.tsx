import { useState } from "react";
import { finance } from "../api/client";
import type { Month } from "../api/types";
import { addMonths, currentMonth } from "../lib/format";

/** Export comptable (SPEC §5.6 / §8.1) : le serveur génère l'Excel et le ZIP. */
export function AccountingExportPage({ clients }: { clients: Array<{ id: string; name: string }> }) {
  const now = currentMonth();
  const [from, setFrom] = useState<Month>(addMonths(now, -1));
  const [to, setTo] = useState<Month>(addMonths(now, -1));
  const [client, setClient] = useState("");
  const [expenses, setExpenses] = useState(true);
  const quick = (q: "last" | "cur" | "year" | "lastyear") => {
    const y = Number(now.slice(0, 4));
    const r: Record<string, [Month, Month]> = {
      last: [addMonths(now, -1), addMonths(now, -1)],
      cur: [now, now],
      year: [`${y}-01` as Month, now],
      lastyear: [`${y - 1}-01` as Month, `${y - 1}-12` as Month],
    };
    setFrom(r[q][0]);
    setTo(r[q][1]);
  };
  const p = { from, to, client: client || undefined, expenses };
  return (
    <section className="fin-page">
      <h1>Export comptable</h1>
      <p className="fin-sub">
        Préparez le dossier pour votre comptable : un fichier Excel récapitulatif et toutes les factures et justificatifs, rangés
        par client et par mois.
      </p>
      <div className="fin-panel">
        <div className="fin-row">
          <label>
            Du mois
            <input type="month" value={from} onChange={(e) => setFrom(e.target.value as Month)} />
          </label>
          <label>
            Au mois
            <input type="month" value={to} onChange={(e) => setTo(e.target.value as Month)} />
          </label>
          <label>
            Client
            <select value={client} onChange={(e) => setClient(e.target.value)}>
              <option value="">Tous les clients</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="fin-row">
          <div className="fin-seg">
            <button onClick={() => quick("last")}>Mois dernier</button>
            <button onClick={() => quick("cur")}>Ce mois</button>
            <button onClick={() => quick("year")}>Cette année</button>
            <button onClick={() => quick("lastyear")}>Année dernière</button>
          </div>
          <label className="fin-check">
            <input type="checkbox" checked={expenses} onChange={(e) => setExpenses(e.target.checked)} />
            Inclure les dépenses
          </label>
        </div>
      </div>
      <div className="fin-row fin-row--end">
        <button className="fin-btn fin-btn--ghost" onClick={() => void finance.downloadAccountingExport({ ...p, kind: "xlsx" })}>
          Excel seul (.xlsx)
        </button>
        <button className="fin-btn" onClick={() => void finance.downloadAccountingExport({ ...p, kind: "zip" })}>
          Télécharger le dossier comptable (.zip)
        </button>
      </div>
    </section>
  );
}
