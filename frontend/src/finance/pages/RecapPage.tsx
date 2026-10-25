import { useState } from "react";
import { finance } from "../api/client";
import { clientColor, eur, eur2, monthLabel, n } from "../lib/format";
import { useApi } from "../lib/useApi";

/** Récap mensuel (SPEC §5.4) : tableau croisé + relevé détaillé. */
export function RecapPage() {
  const [period, setPeriod] = useState<"year" | "12" | "all">("all");
  const { data } = useApi(() => finance.recap(period), [period]);
  if (!data) return <p className="fin-sub">Chargement…</p>;
  const total = data.detail.reduce((s, m) => s + n(m.revenue), 0);
  const byClient = data.clients
    .map((c) => ({ c, v: data.months.reduce((s, m) => s + n(data.matrix[c.id]?.[m]), 0) }))
    .filter((x) => x.v)
    .sort((a, b) => b.v - a.v);
  const active = data.detail.filter((m) => n(m.revenue));
  const best = active.reduce<(typeof active)[number] | null>((b, m) => (!b || n(m.revenue) > n(b.revenue) ? m : b), null);
  return (
    <section className="fin-page">
      <div className="fin-head">
        <div>
          <h1>Récap mensuel</h1>
          <p className="fin-sub">Ce que vous avez facturé, mois par mois, par client et par projet.</p>
        </div>
        <div className="fin-seg">
          <button aria-pressed={period === "year"} onClick={() => setPeriod("year")}>
            Cette année
          </button>
          <button aria-pressed={period === "12"} onClick={() => setPeriod("12")}>
            12 derniers mois
          </button>
          <button aria-pressed={period === "all"} onClick={() => setPeriod("all")}>
            Depuis le début
          </button>
        </div>
      </div>
      <div className="fin-hero">
        <div className="fin-panel">
          <div className="fin-sub">
            Total facturé {monthLabel(data.months[0])} – {monthLabel(data.months[data.months.length - 1])}
          </div>
          <div className="fin-big fin-num">{eur2.format(total)}</div>
          <div className="fin-split">
            {byClient.map((x) => (
              <span key={x.c.id} style={{ width: `${(x.v / total) * 100}%`, background: clientColor(data.clients, x.c.id) }} />
            ))}
          </div>
          <div className="fin-legend">
            {byClient.map((x) => (
              <span key={x.c.id}>
                <i className="fin-dot" style={{ background: clientColor(data.clients, x.c.id) }} />
                {x.c.name} <b>{eur.format(x.v)}</b> <span className="fin-sub">({Math.round((x.v / total) * 100)} %)</span>
              </span>
            ))}
          </div>
        </div>
        <div className="fin-stats">
          <div className="fin-stat">
            <b className="fin-num">{eur.format(active.length ? total / active.length : 0)}</b>
            <span>Moyenne par mois facturé</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{best ? eur.format(n(best.revenue)) : "—"}</b>
            <span>{best ? `Meilleur mois : ${monthLabel(best.month)}` : "Meilleur mois"}</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{byClient.length}</b>
            <span>Clients facturés</span>
          </div>
          <div className="fin-stat">
            <b className="fin-num">{active.length}</b>
            <span>Mois avec facturation</span>
          </div>
        </div>
      </div>
      <div className="fin-panel">
        <h2>Tableau croisé</h2>
        <div className="fin-scroll">
          <table className="fin-table fin-matrix">
            <thead>
              <tr>
                <th>Client</th>
                {data.months.map((m) => (
                  <th key={m} className="r">
                    {monthLabel(m, true)}
                  </th>
                ))}
                <th className="r">Total</th>
              </tr>
            </thead>
            <tbody>
              {byClient.map((x) => (
                <tr key={x.c.id}>
                  <td className="fin-client" style={{ boxShadow: `inset 3px 0 0 ${clientColor(data.clients, x.c.id)}` }}>
                    {x.c.name}
                  </td>
                  {data.months.map((m) => (
                    <td key={m} className="r fin-num">
                      {n(data.matrix[x.c.id]?.[m]) ? eur.format(n(data.matrix[x.c.id][m])) : <span className="fin-sub">·</span>}
                    </td>
                  ))}
                  <td className="r fin-num">
                    <b>{eur.format(x.v)}</b>
                  </td>
                </tr>
              ))}
              <tr className="fin-total">
                <td>Total du mois</td>
                {data.detail.map((m) => (
                  <td key={m.month} className="r fin-num">
                    {n(m.revenue) ? eur.format(n(m.revenue)) : ""}
                  </td>
                ))}
                <td className="r fin-num">{eur.format(total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      {[...data.detail].reverse().map((m) => (
        <div className="fin-panel" key={m.month}>
          <div className="fin-recap-head">
            <h2 style={{ textTransform: "capitalize" }}>{monthLabel(m.month)}</h2>
            <span className="fin-num">{eur2.format(n(m.revenue))}</span>
          </div>
          {m.clients.length ? (
            m.clients.map((c) => (
              <div key={c.client.id}>
                <div className="fin-recap-client">
                  <span>
                    <i className="fin-dot" style={{ background: clientColor(data.clients, c.client.id) }} />
                    {c.client.name}
                  </span>
                  <span className="fin-num">{eur2.format(n(c.revenue))}</span>
                </div>
                {c.projects.map((p) => (
                  <div className="fin-recap-proj" key={p.project.id}>
                    <span>{p.project.name}</span>
                    <span className="fin-num">{eur2.format(n(p.revenue))}</span>
                    <div className="fin-sub">{p.lines.join(" · ")}</div>
                  </div>
                ))}
              </div>
            ))
          ) : (
            <p className="fin-sub">Rien de facturé ce mois-ci.</p>
          )}
        </div>
      ))}
    </section>
  );
}
