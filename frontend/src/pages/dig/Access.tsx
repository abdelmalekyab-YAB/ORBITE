import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../../auth/AuthContext";
import { Avatar, Loading } from "../../components/bits";
import { useUI } from "../../components/UIContext";
import { ApiError, api, post } from "../../lib/api";
import { useApi } from "../../lib/hooks";
import type { Project } from "../../lib/types";

type Status = "active" | "invited" | "disabled";
interface AdminUser {
  id: number;
  email: string;
  name: string;
  initials: string;
  job: "admin" | "pm" | "dev" | "client";
  organization: { id: number; name: string; kind: string } | null;
  is_active: boolean;
  status: Status;
  projects: string[];
}
interface Org {
  id: number;
  name: string;
  is_active: boolean;
  users: AdminUser[];
  projects: { key: string; name: string; is_archived: boolean }[];
}

const JOBS = { admin: "Administrateur", pm: "Chef de projet", dev: "Développeur" } as const;

function useAction() {
  const { toast, bump } = useUI();
  return async (fn: () => Promise<unknown>, done: string, after?: () => void) => {
    try {
      await fn();
      toast(done);
      bump();
      after?.();
      return true;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Action impossible");
      return false;
    }
  };
}

function StatusBall({ s }: { s: Status }) {
  return s === "invited" ? (
    <span className="ball dig">Invitation envoyée</span>
  ) : s === "disabled" ? (
    <span className="ball done">Désactivé</span>
  ) : (
    <span className="ball you">Actif</span>
  );
}

function UserActions({ u, onEdit }: { u: AdminUser; onEdit: () => void }) {
  const me = useMe();
  const act = useAction();
  return (
    <td style={{ whiteSpace: "nowrap" }}>
      <button className="btn ghost sm" onClick={onEdit}>
        Modifier
      </button>
      {u.status === "invited" ? (
        <button
          className="btn ghost sm"
          onClick={() => act(() => post(`/users/${u.id}/resend-invite`, {}), `Invitation renvoyée à ${u.email}`)}
        >
          Renvoyer
        </button>
      ) : (
        <button
          className="btn ghost sm"
          disabled={!u.is_active}
          onClick={() => act(() => post(`/users/${u.id}/reset-password`, {}), `E-mail de réinitialisation envoyé à ${u.email}`)}
        >
          Mot de passe
        </button>
      )}
      {u.id !== me.id && (
        <button
          className="btn ghost sm"
          onClick={() =>
            act(
              () => post(`/users/${u.id}/${u.is_active ? "deactivate" : "activate"}`, {}),
              u.is_active ? `${u.name} désactivé` : `${u.name} réactivé`,
            )
          }
        >
          {u.is_active ? "Désactiver" : "Réactiver"}
        </button>
      )}
      {u.id !== me.id && (
        <button
          className="btn ghost sm"
          style={{ color: "var(--rose)" }}
          onClick={() =>
            window.confirm(
              `Supprimer le compte de ${u.name} ? Ses données personnelles seront effacées (RGPD) ; l'historique des demandes est conservé de façon anonyme.`,
            ) && act(() => api(`/users/${u.id}`, { method: "DELETE" }), "Compte supprimé")
          }
        >
          Supprimer
        </button>
      )}
    </td>
  );
}

function EditRow({ u, cols, onClose }: { u: AdminUser; cols: number; onClose: () => void }) {
  const [v, setV] = useState({ name: u.name, email: u.email });
  const act = useAction();
  return (
    <tr>
      <td colSpan={cols} style={{ background: "var(--vsoft)" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
          <label className="field" style={{ flex: 1, minWidth: 140 }}>
            Nom
            <input value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
          </label>
          <label className="field" style={{ flex: 1, minWidth: 180 }}>
            E-mail
            <input type="email" value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} />
          </label>
          <button
            className="btn grad sm"
            onClick={() => act(() => api(`/users/${u.id}`, { method: "PATCH", body: JSON.stringify(v) }), "Enregistré", onClose)}
          >
            ✓ Enregistrer
          </button>
          <button className="btn ghost sm" onClick={onClose}>
            Annuler
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function Access() {
  const users = useApi<AdminUser[]>("/users?kind=digitalia");
  const orgs = useApi<Org[]>("/organizations");
  const projects = useApi<Project[]>("/projects?include_archived=1");
  if (!users.data || !orgs.data || !projects.data) return <Loading />;
  const team = users.data;
  return (
    <>
      <h1 style={{ marginBottom: 4 }}>Accès</h1>
      <p className="hint" style={{ marginBottom: 18 }}>
        Qui accède à Orbit et à quoi : l'équipe Digitalia, les clients et leurs utilisateurs, les projets.
      </p>
      <div className="settings" style={{ maxWidth: "none" }}>
        <Team team={team} />
        <Clients orgs={orgs.data} />
        <Projects projects={projects.data} team={team} orgs={orgs.data} />
      </div>
    </>
  );
}

function Team({ team }: { team: AdminUser[] }) {
  const me = useMe();
  const act = useAction();
  const [editing, setEditing] = useState<number | null>(null);
  const [f, setF] = useState({ name: "", email: "", job: "dev" });
  return (
    <div className="card">
      <h2>
        Équipe Digitalia <span className="cnt">{team.filter((u) => u.is_active).length} membres actifs</span>
      </h2>
      <p className="hint" style={{ marginBottom: 10 }}>
        Développeur : cockpit, kanban, projets, équipe. Chef de projet : + triage et réglages. Administrateur : + finances et
        gestion des accès.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Membre</th>
              <th>E-mail</th>
              <th>Rôle</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {team.map((u) => [
              <tr key={u.id} style={u.is_active ? undefined : { opacity: 0.5 }}>
                <td>
                  <Avatar user={u} small /> <b>{u.name}</b>
                </td>
                <td className="hint">{u.email}</td>
                <td>
                  <select
                    className="fin-in"
                    style={{ width: "auto", textAlign: "left" }}
                    value={u.job}
                    disabled={u.id === me.id}
                    aria-label={`Rôle de ${u.name}`}
                    onChange={(e) =>
                      act(
                        () => api(`/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ job: e.target.value }) }),
                        "Rôle mis à jour",
                      )
                    }
                  >
                    {Object.entries(JOBS).map(([k, l]) => (
                      <option key={k} value={k}>
                        {l}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <StatusBall s={u.status} />
                </td>
                <UserActions u={u} onEdit={() => setEditing(u.id)} />
              </tr>,
              editing === u.id && <EditRow key={`e${u.id}`} u={u} cols={5} onClose={() => setEditing(null)} />,
            ])}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12, alignItems: "end" }}>
        <label className="field" style={{ flex: 1, minWidth: 140 }}>
          Nom
          <input value={f.name} placeholder="Prénom Nom" onChange={(e) => setF({ ...f, name: e.target.value })} />
        </label>
        <label className="field" style={{ flex: 1, minWidth: 180 }}>
          E-mail
          <input
            type="email"
            value={f.email}
            placeholder="prenom@digitalia.io"
            onChange={(e) => setF({ ...f, email: e.target.value })}
          />
        </label>
        <label className="field">
          Rôle
          <select value={f.job} onChange={(e) => setF({ ...f, job: e.target.value })}>
            {Object.entries(JOBS).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <button
          className="btn grad"
          disabled={!f.name.trim() || !f.email.includes("@")}
          onClick={() =>
            act(
              () => post("/users", f),
              `Invitation envoyée à ${f.email}`,
              () => setF({ name: "", email: "", job: "dev" }),
            )
          }
        >
          ＋ Inviter
        </button>
      </div>
      <p className="hint" style={{ marginTop: 6 }}>
        La personne reçoit un e-mail pour créer son mot de passe.
      </p>
    </div>
  );
}

function Clients({ orgs }: { orgs: Org[] }) {
  const act = useAction();
  const [editing, setEditing] = useState<number | null>(null);
  const [invite, setInvite] = useState<Record<number, { name: string; email: string }>>({});
  const [client, setClient] = useState({ name: "", contact_name: "", contact_email: "" });

  function toggleAccess(u: AdminUser, key: string) {
    const next = u.projects.includes(key) ? u.projects.filter((k) => k !== key) : [...u.projects, key];
    act(
      () => api(`/users/${u.id}/project-access`, { method: "PUT", body: JSON.stringify({ projects: next }) }),
      "Accès mis à jour",
    );
  }

  return (
    <div className="card">
      <h2>Clients et accès</h2>
      <p className="hint" style={{ marginBottom: 10 }}>
        Un utilisateur client ne voit que les projets qu'on lui ouvre. Un client peut avoir plusieurs projets et plusieurs
        utilisateurs.
      </p>
      {orgs.map((o) => {
        const f = invite[o.id] ?? { name: "", email: "" };
        return (
          <div key={o.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--line2)" }}>
            <h3>
              {o.name}{" "}
              <span className="hint" style={{ fontWeight: 500 }}>
                · {o.projects.map((p) => p.name).join(", ") || "aucun projet"}
              </span>
            </h3>
            <table style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>Utilisateur</th>
                  <th>E-mail</th>
                  <th>Accès aux projets</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {o.users.map((u) => [
                  <tr key={u.id} style={u.is_active ? undefined : { opacity: 0.5 }}>
                    <td>
                      <Avatar user={u} small /> <b>{u.name}</b>
                      {u.status === "invited" && (
                        <>
                          {" "}
                          <span className="ball dig" style={{ fontSize: 10.5 }}>
                            invité
                          </span>
                        </>
                      )}
                    </td>
                    <td className="hint">{u.email}</td>
                    <td>
                      <div className="chips" style={{ gap: 4 }}>
                        {o.projects
                          .filter((p) => !p.is_archived)
                          .map((p) => (
                            <button
                              key={p.key}
                              className={`chip ${u.projects.includes(p.key) ? "on" : ""}`}
                              style={{ padding: "3px 9px", fontSize: 11.5 }}
                              aria-pressed={u.projects.includes(p.key)}
                              onClick={() => toggleAccess(u, p.key)}
                            >
                              {p.name}
                            </button>
                          ))}
                      </div>
                    </td>
                    <UserActions u={u} onEdit={() => setEditing(u.id)} />
                  </tr>,
                  editing === u.id && <EditRow key={`e${u.id}`} u={u} cols={4} onClose={() => setEditing(null)} />,
                ])}
              </tbody>
            </table>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, alignItems: "end" }}>
              <label className="field" style={{ flex: 1, minWidth: 140 }}>
                <input
                  aria-label={`Nom (${o.name})`}
                  value={f.name}
                  placeholder="Prénom Nom"
                  onChange={(e) => setInvite({ ...invite, [o.id]: { ...f, name: e.target.value } })}
                />
              </label>
              <label className="field" style={{ flex: 1, minWidth: 180 }}>
                <input
                  aria-label={`E-mail (${o.name})`}
                  type="email"
                  value={f.email}
                  placeholder="email@client.fr"
                  onChange={(e) => setInvite({ ...invite, [o.id]: { ...f, email: e.target.value } })}
                />
              </label>
              <button
                className="btn sm"
                disabled={!f.name.trim() || !f.email.includes("@")}
                onClick={() =>
                  act(
                    () => post("/users", { ...f, organization: o.id }),
                    `Invitation envoyée à ${f.email}`,
                    () => setInvite({ ...invite, [o.id]: { name: "", email: "" } }),
                  )
                }
              >
                ＋ Inviter un utilisateur
              </button>
            </div>
          </div>
        );
      })}
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line2)" }}>
        <h3 style={{ marginBottom: 8 }}>Nouveau client</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
          <label className="field" style={{ flex: 1, minWidth: 160 }}>
            Nom de l'entreprise
            <input
              value={client.name}
              placeholder="Ex. : Atlas Énergie"
              onChange={(e) => setClient({ ...client, name: e.target.value })}
            />
          </label>
          <label className="field" style={{ flex: 1, minWidth: 160 }}>
            Premier contact (nom)
            <input
              value={client.contact_name}
              placeholder="Prénom Nom"
              onChange={(e) => setClient({ ...client, contact_name: e.target.value })}
            />
          </label>
          <label className="field" style={{ flex: 1, minWidth: 180 }}>
            E-mail du contact
            <input
              type="email"
              value={client.contact_email}
              placeholder="contact@client.fr"
              onChange={(e) => setClient({ ...client, contact_email: e.target.value })}
            />
          </label>
          <button
            className="btn grad"
            disabled={!client.name.trim() || !client.contact_email.includes("@")}
            onClick={() =>
              act(
                () => post("/organizations", client),
                `Client ${client.name} créé, invitation envoyée`,
                () => setClient({ name: "", contact_name: "", contact_email: "" }),
              )
            }
          >
            ＋ Créer le client
          </button>
        </div>
        <p className="hint" style={{ marginTop: 6 }}>
          Le contact reçoit une invitation ; vous lui ouvrirez des projets ensuite.
        </p>
      </div>
    </div>
  );
}

function Projects({ projects, team, orgs }: { projects: Project[]; team: AdminUser[]; orgs: Org[] }) {
  const act = useAction();
  const navigate = useNavigate();
  const leads = team.filter((u) => u.is_active);
  const empty = {
    name: "",
    key: "",
    client: "",
    lead: "",
    dev_price: "",
    licence_amount: "",
    licence_start: "",
    description: "",
  };
  const [f, setF] = useState(empty);
  // Valeurs effectives : la liste des clients peut être vide au chargement puis se remplir (base neuve).
  const client = f.client || String(orgs[0]?.id ?? "");
  const lead = f.lead || String(leads[0]?.id ?? "");
  return (
    <div className="card">
      <h2>
        Projets <span className="cnt">{projects.length}</span>
      </h2>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Clé</th>
              <th>Projet</th>
              <th>Client</th>
              <th>Responsable</th>
              <th className="n">Ouvertes</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.key} style={p.is_archived ? { opacity: 0.5 } : undefined}>
                <td>
                  <b>{p.key}</b>
                </td>
                <td>
                  {p.name}
                  <div className="hint">{p.description}</div>
                </td>
                <td>{p.client}</td>
                <td>
                  <select
                    className="fin-in"
                    style={{ width: "auto", textAlign: "left" }}
                    value={p.lead?.id ?? ""}
                    aria-label={`Responsable ${p.name}`}
                    onChange={(e) =>
                      act(
                        () =>
                          api(`/projects/${p.key}`, {
                            method: "PATCH",
                            body: JSON.stringify({ lead: Number(e.target.value) || null }),
                          }),
                        "Responsable mis à jour",
                      )
                    }
                  >
                    <option value="">—</option>
                    {leads.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="n">{p.counts.open}</td>
                <td>
                  {p.is_archived ? <span className="ball done">Archivé</span> : <span className="ball you">En production</span>}
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn ghost sm" onClick={() => navigate(`/dig/projets/${p.key}`)}>
                    Ouvrir
                  </button>
                  <button
                    className="btn ghost sm"
                    onClick={() =>
                      act(
                        () => post(`/projects/${p.key}/${p.is_archived ? "unarchive" : "archive"}`, {}),
                        p.is_archived ? `${p.name} réactivé` : `${p.name} archivé`,
                      )
                    }
                  >
                    {p.is_archived ? "Réactiver" : "Archiver"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line2)" }}>
        <h3 style={{ marginBottom: 8 }}>Nouveau projet</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 8, alignItems: "end" }}>
          <label className="field">
            Nom
            <input value={f.name} placeholder="Ex. : Portail RH" onChange={(e) => setF({ ...f, name: e.target.value })} />
          </label>
          <label className="field">
            Clé (2-6 caractères)
            <input
              value={f.key}
              placeholder="PRH"
              maxLength={6}
              style={{ textTransform: "uppercase" }}
              onChange={(e) => setF({ ...f, key: e.target.value.toUpperCase() })}
            />
          </label>
          <label className="field">
            Client
            <select value={client} onChange={(e) => setF({ ...f, client: e.target.value })}>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Responsable
            <select value={lead} onChange={(e) => setF({ ...f, lead: e.target.value })}>
              {leads.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Prix du dev (€)
            <input
              type="number"
              value={f.dev_price}
              placeholder="0"
              onChange={(e) => setF({ ...f, dev_price: e.target.value })}
            />
          </label>
          <label className="field">
            Licence / mois (€)
            <input
              type="number"
              value={f.licence_amount}
              placeholder="0"
              onChange={(e) => setF({ ...f, licence_amount: e.target.value })}
            />
          </label>
          <label className="field">
            Licence dès
            <input type="month" value={f.licence_start} onChange={(e) => setF({ ...f, licence_start: e.target.value })} />
          </label>
          <label className="field" style={{ gridColumn: "1/-1" }}>
            Description
            <input
              value={f.description}
              placeholder="En une phrase"
              onChange={(e) => setF({ ...f, description: e.target.value })}
            />
          </label>
          <button
            className="btn grad"
            style={{ justifySelf: "start" }}
            disabled={!f.name.trim() || f.key.length < 2 || !client}
            onClick={() =>
              act(
                () =>
                  post("/projects", {
                    ...f,
                    client: Number(client),
                    lead: Number(lead) || null,
                    dev_price: f.dev_price || 0,
                    licence_amount: f.licence_amount || 0,
                  }),
                `Projet ${f.key} créé`,
                () => setF(empty),
              )
            }
          >
            ＋ Créer le projet
          </button>
        </div>
        <p className="hint" style={{ marginTop: 6 }}>
          Les utilisateurs du client reçoivent l'accès au nouveau projet ; vous pourrez l'ajuster dans « Clients et accès ».
        </p>
      </div>
    </div>
  );
}
