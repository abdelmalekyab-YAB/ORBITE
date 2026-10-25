import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar, Empty, Loading } from "../../components/bits";
import ExportButton from "../../components/ExportButton";
import { Legend, MonthBars, NumberInput } from "../../components/FinanceBits";
import { useUI } from "../../components/UIContext";
import { ApiError, api, post } from "../../lib/api";
import { fmtE } from "../../lib/format";
import { fmtM, num, type CostMode, type Overview, type ProjectFinance, type StaffRow } from "../../lib/finance";
import { useApi } from "../../lib/hooks";

/** Écran Finances (admin) — maquette « dFinance ». */
export default function Finance() {
  const { data, reload } = useApi<Overview>("/finance/overview");
  const [month, setMonth] = useState<string | null>(null);
  const navigate = useNavigate();
  if (!data) return <Loading />;
  const m = month ?? data.current;
  const row = data.months.find((x) => x.month === m) ?? data.months[0];
  const margin = num(row.total) - num(row.cost);

  return (
    <>
      <h1 style={{ marginBottom: 4 }}>Finances</h1>
      <p className="hint" style={{ marginBottom: 18 }}>
        Réservé à l'administration. Ce que chaque projet rapporte : prix du développement (en une ou plusieurs échéances) +
        licence mensuelle. Les coûts sont optionnels.
      </p>
      <div className="toolbar">
        <ExportButton
          path={`/finance/export.csv?from=${data.months[0].month}&to=${data.months[data.months.length - 1].month}`}
          filename={`orbit-finances-${data.current}.csv`}
        />
        <span className="hint">Mois :</span>
        {data.months.map((x) => (
          <button key={x.month} className={`chip ${x.month === m ? "on" : ""}`} onClick={() => setMonth(x.month)}>
            {fmtM(x.month)}
          </button>
        ))}
      </div>
      <div className="fin-kpi">
        <div className="fk neon">
          <b>{fmtE(row.total)}</b>
          <span>Recettes {fmtM(m)} · tous projets</span>
        </div>
        <div className="fk">
          <b>{fmtE(data.kpis.licence_monthly)}</b>
          <span>Licences récurrentes / mois</span>
        </div>
        <div className="fk amber">
          <b>{fmtE(data.kpis.dev_to_come)}</b>
          <span>Échéances de dev restant à encaisser</span>
        </div>
        {data.has_cost ? (
          <div className={`fk ${margin >= 0 ? "" : "rose"}`}>
            <b>{fmtE(margin)}</b>
            <span>
              Marge {fmtM(m)} (coûts {fmtE(row.cost)})
            </span>
          </div>
        ) : (
          <div className="fk">
            <b>{fmtE(data.kpis.cashed)}</b>
            <span>Encaissé depuis le début</span>
          </div>
        )}
      </div>

      <h2 style={{ marginBottom: 10 }}>Ce que chaque projet a rapporté depuis le début</h2>
      <div className="g3" style={{ marginBottom: 22, alignItems: "stretch" }}>
        {data.projects.map((p) => {
          const max = Math.max(1, num(p.total) + num(p.to_come));
          const bar = (v: string, c: string) => (
            <i style={{ display: "inline-block", height: "100%", width: `${(num(v) / max) * 100}%`, background: c }} />
          );
          return (
            <div
              className="card"
              key={p.key}
              role="button"
              tabIndex={0}
              style={{ cursor: "pointer" }}
              onClick={() => navigate(`/dig/projets/${p.key}?tab=fin`)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <h2 style={{ margin: 0, fontSize: 18 }}>{p.name}</h2>
                <span className="hint">{p.client}</span>
              </div>
              <div
                style={{
                  fontFamily: "'Space Grotesk'",
                  fontSize: 32,
                  fontWeight: 700,
                  color: "var(--neon)",
                  letterSpacing: "-.02em",
                  margin: "10px 0 2px",
                }}
              >
                {fmtE(p.total)}
              </div>
              <div className="hint" style={{ marginBottom: 12 }}>
                encaissés depuis le début{p.has_cost && num(p.cost) ? ` · marge ${fmtE(p.margin)}` : ""}
              </div>
              <div
                style={{
                  display: "flex",
                  height: 10,
                  borderRadius: 99,
                  overflow: "hidden",
                  background: "var(--line2)",
                  marginBottom: 10,
                }}
              >
                {bar(p.dev_paid, "var(--violet)")}
                {bar(p.licence, "var(--neon)")}
                {bar(p.quotes_paid, "var(--cyan)")}
                {bar(p.to_come, "var(--line)")}
              </div>
              <div className="kv" style={{ gridTemplateColumns: "auto 1fr", fontSize: 12.5 }}>
                <Legend color="var(--violet)">Développement</Legend>
                <span style={{ textAlign: "right" }}>
                  {fmtE(p.dev_paid)} <span className="muted">/ {fmtE(p.dev_total)}</span>
                </span>
                <Legend color="var(--neon)">Licence</Legend>
                <span style={{ textAlign: "right" }}>
                  {fmtE(p.licence)}{" "}
                  <span className="muted">
                    · {p.licence_months} mois × {fmtE(p.licence_monthly)}
                  </span>
                </span>
                <Legend color="var(--cyan)">Évolutions vendues</Legend>
                <span style={{ textAlign: "right" }}>
                  {fmtE(p.quotes_paid)} <span className="muted">· {p.quotes_count} devis</span>
                </span>
                <Legend color="var(--line)">Reste à encaisser</Legend>
                <span style={{ textAlign: "right" }}>{fmtE(p.to_come)}</span>
                {num(p.pending_quotes) > 0 && (
                  <>
                    <span style={{ color: "var(--amber)" }}>⏳ Devis en attente</span>
                    <span style={{ textAlign: "right", color: "var(--amber)" }}>{fmtE(p.pending_quotes)}</span>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <h2>
          Mois par mois <span className="cnt">recettes{data.has_cost ? " et coûts" : ""}</span>
        </h2>
        <MonthBars
          months={data.months.map((x) => ({ month: x.month, revenue: num(x.total), cost: num(x.cost) }))}
          current={data.current}
          selected={m}
          onSelect={setMonth}
          showCost={data.has_cost}
        />
        <div style={{ overflowX: "auto", marginTop: 14 }}>
          <table>
            <thead>
              <tr>
                <th>Projet</th>
                {data.months.map((x) => (
                  <th key={x.month} className="n" style={x.month === m ? { color: "var(--neon)" } : undefined}>
                    {fmtM(x.month)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.projects.map((p) => (
                <tr key={p.key}>
                  <td>
                    <b>{p.name}</b>
                  </td>
                  {data.months.map((x) => {
                    const r = num(x.revenue[p.key]);
                    return (
                      <td key={x.month} className="n" style={x.month === m ? { background: "var(--nsoft)" } : undefined}>
                        {r ? fmtE(r) : <span className="muted">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr>
                <td>
                  <b>Total recettes</b>
                </td>
                {data.months.map((x) => (
                  <td
                    key={x.month}
                    className="n"
                    style={{ fontWeight: 700, ...(x.month === m ? { background: "var(--nsoft)" } : {}) }}
                  >
                    {fmtE(x.total)}
                  </td>
                ))}
              </tr>
              {data.has_cost && (
                <>
                  <tr>
                    <td className="muted">Coûts</td>
                    {data.months.map((x) => (
                      <td key={x.month} className="n muted">
                        {num(x.cost) ? fmtE(x.cost) : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td>
                      <b>Marge</b>
                    </td>
                    {data.months.map((x) => (
                      <td
                        key={x.month}
                        className="n"
                        style={{ fontWeight: 700, color: num(x.margin) < 0 ? "var(--rose)" : "var(--neon)" }}
                      >
                        {fmtE(x.margin)}
                      </td>
                    ))}
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <h2 style={{ marginBottom: 10 }}>
        Paramètres par projet{" "}
        <span className="cnt" style={{ fontFamily: "Inter", fontSize: 12, color: "var(--mute)" }}>
          prix, échéances, licence, coûts
        </span>
      </h2>
      <div className="g3" style={{ marginBottom: 18, alignItems: "start" }}>
        {data.projects.map((p) => (
          <ProjectParams key={p.key} projectKey={p.key} tjm={data.default_tjm} onChange={reload} />
        ))}
      </div>
      <div className="g2">
        <Staff projects={data.projects.map((p) => ({ key: p.key, name: p.name }))} onChange={reload} />
        <ToQuote data={data} onChange={reload} />
      </div>
    </>
  );
}

function useSave() {
  const { toast } = useUI();
  return async (fn: () => Promise<unknown>, after?: () => void) => {
    try {
      await fn();
      after?.();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Enregistrement impossible");
    }
  };
}

function ProjectParams({ projectKey, tjm, onChange }: { projectKey: string; tjm: string; onChange: () => void }) {
  const { data: f, reload } = useApi<ProjectFinance>(`/finance/projects/${projectKey}`);
  const save = useSave();
  if (!f)
    return (
      <div className="card">
        <Loading />
      </div>
    );
  const refresh = () => {
    reload();
    onChange();
  };
  const put = (body: Record<string, unknown>) =>
    save(() => api(`/finance/projects/${projectKey}`, { method: "PUT", body: JSON.stringify(body) }), refresh);
  const inst = (id: number, body: Record<string, unknown>) =>
    save(
      () => api(`/finance/projects/${projectKey}/installments/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
      refresh,
    );
  const paid = f.installments.filter((e) => e.is_paid).reduce((a, e) => a + num(e.amount), 0);
  const devPrice = num(f.dev_price);

  return (
    <div className="card" data-testid={`params-${projectKey}`}>
      <h2 style={{ marginBottom: 4 }}>
        {f.name} <span className="cnt">{f.client}</span>
      </h2>
      <div className="kv" style={{ margin: "10px 0" }}>
        <span>Prix du dev</span>
        <span>
          <NumberInput label={`Prix du dev ${f.name}`} value={f.dev_price} onCommit={(v) => put({ dev_price: v || 0 })} /> €
        </span>
        <span>Licence / mois</span>
        <span>
          <NumberInput label={`Licence ${f.name}`} value={f.licence_amount} onCommit={(v) => put({ licence_amount: v || 0 })} /> €
          dès{" "}
          <input
            className="fin-in"
            type="month"
            style={{ width: "auto", textAlign: "left" }}
            aria-label={`Début de licence ${f.name}`}
            value={f.licence_start ?? ""}
            onChange={(e) => put({ licence_start: e.target.value || null })}
          />
        </span>
        <span>Fin de licence</span>
        <span>
          <input
            className="fin-in"
            type="month"
            style={{ width: "auto", textAlign: "left" }}
            aria-label={`Fin de licence ${f.name}`}
            value={f.licence_end ?? ""}
            onChange={(e) => put({ licence_end: e.target.value || null })}
          />{" "}
          <span className="hint">vide = en cours</span>
        </span>
      </div>
      <h3 style={{ margin: "8px 0 6px" }}>
        Échéances du dev{" "}
        <span className="hint" style={{ fontWeight: 500 }}>
          · {fmtE(paid)} / {fmtE(devPrice)} encaissés
        </span>
      </h3>
      <div className="prog neon" style={{ marginBottom: 8 }}>
        <i style={{ width: `${devPrice ? Math.min(100, (paid / devPrice) * 100) : 0}%` }} />
      </div>
      {f.installments.map((e) => (
        <div key={e.id} style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 6 }}>
          <input
            type="checkbox"
            checked={e.is_paid}
            title="Encaissée"
            aria-label="Encaissée"
            onChange={(ev) => inst(e.id, { is_paid: ev.target.checked })}
          />
          <input
            className="fin-in"
            type="date"
            style={{ width: "auto", textAlign: "left" }}
            value={e.due_on}
            aria-label="Date d'échéance"
            onChange={(ev) => ev.target.value && inst(e.id, { due_on: ev.target.value })}
          />
          <NumberInput label="Montant" value={e.amount} onCommit={(v) => num(v) > 0 && inst(e.id, { amount: v })} />
          <span className="hint">€</span>
          <button
            className="btn ghost sm"
            aria-label="Supprimer l'échéance"
            onClick={() => save(() => api(`/finance/projects/${projectKey}/installments/${e.id}`, { method: "DELETE" }), refresh)}
          >
            ✕
          </button>
        </div>
      ))}
      <button
        className="btn ghost sm"
        onClick={() =>
          save(
            () =>
              post(`/finance/projects/${projectKey}/installments`, {
                due_on: new Date().toISOString().slice(0, 10),
                amount: Math.max(1, devPrice - f.installments.reduce((a, e) => a + num(e.amount), 0)),
              }),
            refresh,
          )
        }
      >
        ＋ Échéance
      </button>

      <h3 style={{ margin: "14px 0 6px" }}>
        Coûts{" "}
        <span className="hint" style={{ fontWeight: 500 }}>
          · optionnel
        </span>
      </h3>
      <select
        className="fin-in"
        style={{ width: "100%", textAlign: "left" }}
        value={f.cost_mode}
        aria-label={`Mode de coût ${f.name}`}
        onChange={(e) => put({ cost_mode: e.target.value as CostMode })}
      >
        <option value="none">Ne pas suivre les coûts</option>
        <option value="people">Salaires par personne (affectation %)</option>
        <option value="monthly">Montant mensuel pour ce projet</option>
        <option value="days">Jours × TJM (coût unique)</option>
      </select>
      {f.cost_mode === "monthly" && (
        <div className="kv" style={{ marginTop: 8 }}>
          <span>Par mois</span>
          <span>
            <NumberInput label="Coût mensuel" value={f.cost_monthly} onCommit={(v) => put({ cost_monthly: v || 0 })} /> €
          </span>
        </div>
      )}
      {f.cost_mode === "days" && (
        <div className="kv" style={{ marginTop: 8 }}>
          <span>Jours</span>
          <span>
            <NumberInput label="Jours" value={f.cost_days} onCommit={(v) => put({ cost_days: v || 0 })} />
          </span>
          <span>TJM</span>
          <span>
            <NumberInput label="TJM" value={f.cost_tjm ?? tjm} onCommit={(v) => put({ cost_tjm: v || null })} /> €
          </span>
          <span>Comptabilisé en</span>
          <span>
            <input
              className="fin-in"
              type="month"
              style={{ width: "auto", textAlign: "left" }}
              aria-label="Mois comptabilisé"
              value={f.cost_month ?? ""}
              onChange={(e) => put({ cost_month: e.target.value || null })}
            />
          </span>
          <span>Total</span>
          <span>
            <b>{fmtE(num(f.cost_days) * num(f.cost_tjm ?? tjm))}</b>
          </span>
        </div>
      )}
      {f.cost_mode === "people" && (
        <div className="hint" style={{ marginTop: 8 }}>
          <b style={{ color: "var(--ink)" }}>= {fmtE(f.people_cost)} / mois</b> · réglez les affectations ci-dessous
        </div>
      )}
    </div>
  );
}

function Staff({ projects, onChange }: { projects: { key: string; name: string }[]; onChange: () => void }) {
  const { data, setData } = useApi<StaffRow[]>("/finance/staff");
  const save = useSave();
  const { toast } = useUI();
  if (!data)
    return (
      <div className="card">
        <Loading />
      </div>
    );
  const update = (row: StaffRow, patch: Partial<StaffRow>) =>
    save(async () => {
      const next = { ...row, ...patch };
      const rows = await api<StaffRow[]>("/finance/staff", {
        method: "PUT",
        body: JSON.stringify([{ user: next.user, monthly_salary: next.monthly_salary || 0, allocations: next.allocations }]),
      });
      setData(rows);
      const w = rows.find((r) => r.user === row.user)?.warning;
      if (w) toast(`${row.name} : ${w}`);
    }, onChange);

  return (
    <div className="card">
      <h2>
        Salaires et affectations <span className="cnt">pour le mode « par personne »</span>
      </h2>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Personne</th>
              <th className="n">Salaire / mois</th>
              {projects.map((p) => (
                <th key={p.key} className="n">
                  {p.name} %
                </th>
              ))}
              <th className="n">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.user}>
                <td>
                  <Avatar
                    user={{
                      id: r.user,
                      name: r.name,
                      initials: r.name
                        .split(" ")
                        .map((x) => x[0])
                        .join("")
                        .slice(0, 2),
                      job: "dev",
                    }}
                    small
                  />{" "}
                  {r.name}
                </td>
                <td className="n">
                  <NumberInput
                    label={`Salaire ${r.name}`}
                    value={r.monthly_salary}
                    onCommit={(v) => update(r, { monthly_salary: v })}
                  />{" "}
                  €
                </td>
                {projects.map((p) => (
                  <td key={p.key} className="n">
                    <NumberInput
                      width={64}
                      label={`${r.name} ${p.name} %`}
                      value={r.allocations[p.key] ?? 0}
                      onCommit={(v) =>
                        update(r, { allocations: { ...r.allocations, [p.key]: Math.max(0, Math.min(100, Math.round(num(v)))) } })
                      }
                    />
                  </td>
                ))}
                <td className={`n ${r.total > 100 ? "late" : ""}`} title={r.warning ?? undefined}>
                  {r.total} %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint" style={{ marginTop: 8 }}>
        Le total peut être inférieur à 100 % (temps non affecté à un projet sous licence). Au-delà de 100 %, un avertissement
        s'affiche.
      </p>
    </div>
  );
}

function ToQuote({ data, onChange }: { data: Overview; onChange: () => void }) {
  const save = useSave();
  const { openTicket } = useUI();
  const potential = data.to_quote.filter((t) => t.billing === "quote").reduce((a, t) => a + num(t.potential), 0);
  return (
    <div className="card">
      <h2>
        Évolutions à chiffrer <span className="cnt">aide au devis</span>
      </h2>
      {data.to_quote.length ? (
        <>
          <table>
            <thead>
              <tr>
                <th>Demande</th>
                <th className="n">Jours</th>
                <th className="n">Chiffrage</th>
                <th>Facturation</th>
              </tr>
            </thead>
            <tbody>
              {data.to_quote.map((t) => (
                <tr key={t.id}>
                  <td>
                    <a onClick={() => openTicket(t.id)}>{t.title}</a>
                    <br />
                    <span className="hint">{t.project}</span>
                  </td>
                  <td className="n">
                    <NumberInput
                      width={64}
                      step="0.5"
                      label={`Estimation ${t.ref}`}
                      value={t.estimate_days}
                      onCommit={(v) =>
                        save(
                          () => api(`/tickets/${t.id}`, { method: "PATCH", body: JSON.stringify({ estimate_days: v || null }) }),
                          onChange,
                        )
                      }
                    />
                  </td>
                  <td className="n">{fmtE(t.potential)}</td>
                  <td>
                    <select
                      className="fin-in"
                      style={{ width: "auto", textAlign: "left" }}
                      value={t.billing ?? ""}
                      aria-label={`Facturation ${t.ref}`}
                      onChange={(e) =>
                        save(
                          () =>
                            api(`/tickets/${t.id}`, {
                              method: "PATCH",
                              body: JSON.stringify({ billing: e.target.value || null }),
                            }),
                          onChange,
                        )
                      }
                    >
                      <option value="">—</option>
                      <option value="licence">Inclus licence</option>
                      <option value="quote">Devis</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint" style={{ marginTop: 8 }}>
            TJM de référence pour les devis :{" "}
            <NumberInput
              label="TJM de référence"
              value={data.default_tjm}
              onCommit={(v) =>
                num(v) > 0 &&
                save(() => api("/finance/settings", { method: "PUT", body: JSON.stringify({ default_tjm: v }) }), onChange)
              }
            />{" "}
            € — {fmtE(potential)} de devis potentiels. Ces estimations n'entrent jamais dans les recettes.
          </p>
        </>
      ) : (
        <Empty title="Rien à chiffrer" />
      )}
    </div>
  );
}
