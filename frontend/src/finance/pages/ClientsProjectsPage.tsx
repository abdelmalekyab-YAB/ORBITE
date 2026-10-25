import { useState } from "react";
import { finance } from "../api/client";
import type { BillingProfile, BillingType, ProfileStatus } from "../api/types";
import { ConfirmInline } from "../components/ConfirmInline";
import { currentMonth, eur, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";
import { ProjectSheetDialog } from "./ProjectSheetDialog";

/**
 * Clients & projets (SPEC §5.7).
 * La création de clients/projets passe par les écrans existants d'Orbit ; ici on gère le PROFIL de facturation
 * (type, montants, dates, statut) d'un projet Orbit existant.
 */
export function ClientsProjectsPage({
  orbitProjects,
}: {
  orbitProjects: Array<{ id: number; name: string; client_id: string; client_name: string }>;
}) {
  const { data, reload } = useApi(() => finance.profiles());
  const [sheet, setSheet] = useState<number | null>(null);
  const [del, setDel] = useState<number | null>(null);
  const [edit, setEdit] = useState<Partial<BillingProfile> | null>(null);
  const profiles = data ?? [];
  const byClient = profiles.reduce<Record<string, BillingProfile[]>>(
    (a, p) => ({ ...a, [p.client_name]: [...(a[p.client_name] || []), p] }),
    {},
  );
  const without = orbitProjects.filter((p) => !profiles.some((b) => b.project === p.id));
  const save = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const body = {
      project: Number(fd.get("project")),
      billing_type: fd.get("billing_type") as BillingType,
      status: fd.get("status") as ProfileStatus,
      monthly_amount: String(fd.get("monthly_amount") || 0),
      quote_amount: fd.get("quote_amount") ? String(fd.get("quote_amount")) : null,
      cost: String(fd.get("cost") || 0),
      start_month: String(fd.get("start_month")) as never,
      end_month: String(fd.get("end_month") || "") as never,
      note: String(fd.get("note") || ""),
    };
    if (edit?.id) await finance.updateProfile(edit.id, body);
    else await finance.createProfile(body);
    setEdit(null);
    reload();
  };
  return (
    <section className="fin-page">
      <h1>Clients &amp; projets</h1>
      <p className="fin-sub">Donnez un profil de facturation à vos projets Orbit : montant fixe mensuel ou sur devis.</p>
      <div className="fin-panel">
        <h2>{edit?.id ? "Modifier le profil" : "Nouveau profil de facturation"}</h2>
        <form onSubmit={save} className="fin-form" key={edit?.id ?? "new"}>
          <div className="fin-row">
            <label>
              Projet Orbit
              <select name="project" required defaultValue={edit?.project ?? ""} disabled={!!edit?.id}>
                {edit?.id ? (
                  <option value={edit.project}>{edit.project_name}</option>
                ) : (
                  <>
                    <option value="">—</option>
                    {without.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.client_name}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </label>
            <label>
              Statut
              <select name="status" defaultValue={edit?.status ?? "validated"}>
                <option value="validated">Validé par le client</option>
                <option value="proposal">Proposition envoyée, pas encore validée</option>
              </select>
            </label>
            <label>
              Type
              <select name="billing_type" defaultValue={edit?.billing_type ?? "fixed"}>
                <option value="fixed">Montant fixe chaque mois</option>
                <option value="quote">Sur devis / variable</option>
              </select>
            </label>
          </div>
          <div className="fin-row">
            <label>
              Montant mensuel HT (€)
              <input name="monthly_amount" type="number" step="0.01" min="0" defaultValue={edit?.monthly_amount ?? ""} />
            </label>
            <label>
              Montant total du devis HT (€)
              <input name="quote_amount" type="number" step="0.01" min="0" defaultValue={edit?.quote_amount ?? ""} />
            </label>
            <label>
              Coût (mensuel si fixe, total si devis)
              <input name="cost" type="number" step="0.01" min="0" defaultValue={edit?.cost ?? ""} />
            </label>
          </div>
          <div className="fin-row">
            <label>
              Début
              <input name="start_month" type="month" required defaultValue={edit?.start_month ?? currentMonth()} />
            </label>
            <label>
              Fin (optionnel)
              <input name="end_month" type="month" defaultValue={edit?.end_month ?? ""} />
            </label>
            <label>
              Note
              <input name="note" defaultValue={edit?.note ?? ""} placeholder="Réf. devis, échéancier, maintenance…" />
            </label>
            <button className="fin-btn" type="submit">
              {edit?.id ? "Enregistrer" : "Créer le profil"}
            </button>
            {edit && (
              <button type="button" className="fin-btn fin-btn--ghost" onClick={() => setEdit(null)}>
                Annuler
              </button>
            )}
          </div>
        </form>
      </div>
      <div className="fin-grid">
        {Object.entries(byClient).map(([client, list]) => (
          <div className="fin-panel fin-client-card" key={client}>
            <h3>{client}</h3>
            {list.map((p) => (
              <div className="fin-proj" key={p.id}>
                <div className="fin-proj-top">
                  <span>
                    <button className="fin-pname" onClick={() => setSheet(p.id)}>
                      {p.project_name}
                    </button>
                    {p.status === "proposal" && <span className="fin-tag">Proposition</span>}
                  </span>
                  <span className={`fin-tag fin-tag--${p.billing_type}`}>
                    {p.billing_type === "fixed"
                      ? `${eur.format(n(p.monthly_amount))} / mois`
                      : p.quote_amount
                        ? `Devis ${eur.format(n(p.quote_amount))}`
                        : "Sur devis"}
                  </span>
                </div>
                <div className="fin-sub">
                  Depuis {monthLabel(p.start_month)}
                  {p.end_month ? ` jusqu'à ${monthLabel(p.end_month)}` : ""}
                  {n(p.cost) ? ` · coût ${eur.format(n(p.cost))}${p.billing_type === "fixed" ? "/mois" : " au total"}` : ""}
                </div>
                <div>
                  <button className="fin-link" onClick={() => setSheet(p.id)}>
                    voir le détail
                  </button>
                  <button className="fin-link" onClick={() => setEdit(p)}>
                    modifier
                  </button>
                  <button className="fin-link fin-link--danger" onClick={() => setDel(p.id)}>
                    supprimer
                  </button>
                </div>
                {del === p.id && (
                  <ConfirmInline
                    message={`Supprimer le profil de facturation « ${p.project_name} » et toutes ses factures saisies ?`}
                    onCancel={() => setDel(null)}
                    onConfirm={async () => {
                      await finance.deleteProfile(p.id);
                      setDel(null);
                      reload();
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
      {sheet && <ProjectSheetDialog profileId={sheet} onClose={() => setSheet(null)} />}
    </section>
  );
}
