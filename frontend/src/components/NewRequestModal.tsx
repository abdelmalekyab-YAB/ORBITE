import { useEffect, useState } from "react";
import { useMe } from "../auth/AuthContext";
import { ApiError, formData, post } from "../lib/api";
import { useApi } from "../lib/hooks";
import type { Project, TicketDetail, TicketType } from "../lib/types";
import { AttBar, PendingList, useAttachments } from "./Attachments";
import { TypeTag } from "./bits";
import { useUI } from "./UIContext";

const KINDS: { type: TicketType; e: string; t: string; d: string }[] = [
  { type: "bug", e: "🐞", t: "Quelque chose ne marche pas", d: "Une erreur, un blocage, un comportement anormal." },
  { type: "evolution", e: "✨", t: "Améliorer une fonction existante", d: "Ça marche, mais vous voulez mieux." },
  { type: "feature", e: "🚀", t: "Ajouter quelque chose de nouveau", d: "Une fonctionnalité qui n'existe pas encore." },
  { type: "question", e: "💬", t: "Une question ou un coup de main", d: "Comment faire, un doute, un accès." },
];
const INTERNAL_KIND = { type: "internal" as TicketType, e: "🔒", t: "Tâche interne", d: "Invisible pour le client." };

type Impact = "bloquant" | "genant" | "confort";
const IMPACTS: { k: Impact; t: string; d: string; priority: string }[] = [
  { k: "bloquant", t: "Bloquant", d: "Impossible de travailler", priority: "critical" },
  { k: "genant", t: "Gênant", d: "Ça ralentit, on contourne", priority: "high" },
  { k: "confort", t: "Confort", d: "Ce serait mieux avec", priority: "normal" },
];

export default function NewRequestModal({ defaultProject }: { defaultProject?: string }) {
  const { newRequest, setNewRequest } = useUI();
  if (!newRequest) return null;
  return <ModalBody defaultProject={defaultProject} onClose={() => setNewRequest(false)} />;
}

function ModalBody({ defaultProject, onClose }: { defaultProject?: string; onClose: () => void }) {
  const me = useMe();
  const dig = me.is_digitalia;
  const { toast, bump, openTicket } = useUI();
  const projects = useApi<Project[]>(dig ? "/projects" : null);
  const choices = dig
    ? (projects.data ?? []).map((p) => ({ key: p.key, name: `${p.name} — ${p.client}` }))
    : me.projects.map((p) => ({ key: p.key, name: p.name }));

  const [step, setStep] = useState(1);
  const [project, setProject] = useState(defaultProject ?? me.projects[0]?.key ?? "");
  const [type, setType] = useState<TicketType | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [impact, setImpact] = useState<Impact>("confort");
  const [busy, setBusy] = useState(false);
  const att = useAttachments();

  useEffect(() => {
    if (!project && choices.length) setProject(choices[0].key);
  }, [choices, project]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const kinds = dig ? [...KINDS, INTERNAL_KIND] : KINDS;
  const impactInfo = IMPACTS.find((i) => i.k === impact)!;
  const canNext = step === 1 ? Boolean(type && project) : step === 2 ? title.trim().length > 2 : true;

  async function submit() {
    setBusy(true);
    try {
      const fields = dig
        ? { project, type: type!, title, description, priority: impactInfo.priority }
        : { project, type: type!, title, description, impact };
      const t = await post<TicketDetail>("/tickets", formData(fields, att.files));
      toast(`${t.ref} envoyée — merci !`);
      bump();
      onClose();
      openTicket(t.id);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Envoi impossible");
    } finally {
      setBusy(false);
    }
  }

  const bar = (n: number) => (
    <div className="steps">
      {[1, 2, 3].map((i) => (
        <i key={i} className={i <= n ? "on" : ""} />
      ))}
    </div>
  );

  return (
    <div className="modal show" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="box" role="dialog" aria-modal="true" aria-label="Nouvelle demande">
        {step === 1 && (
          <>
            <h1>De quoi s'agit-il ?</h1>
            <p className="hint">Choisissez ce qui ressemble le plus à votre besoin.</p>
            {bar(1)}
            {dig && projects.data && !choices.length && (
              <p className="banner b-q" role="alert" style={{ marginBottom: 12 }}>
                Aucun projet pour l'instant : créez d'abord un client et un projet dans l'onglet Accès.
              </p>
            )}
            {choices.length > 1 && (
              <label className="field" style={{ marginBottom: 12 }}>
                {dig ? "Projet" : "Pour quel projet ?"}
                <select value={project} onChange={(e) => setProject(e.target.value)}>
                  {choices.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="tiles">
              {kinds.map((k) => (
                <button key={k.type} className={`tile ${type === k.type ? "on" : ""}`} onClick={() => setType(k.type)}>
                  <span className="e">{k.e}</span>
                  <b>{k.t}</b>
                  <span>{k.d}</span>
                </button>
              ))}
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <h1>Racontez-nous</h1>
            <p className="hint">Plus c'est précis, plus c'est rapide à traiter.</p>
            {bar(2)}
            <div style={{ display: "grid", gap: 14 }}>
              <label className="field">
                En une phrase
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={200}
                  autoFocus
                  placeholder={
                    type === "bug" ? "Ex. : Erreur à l'export des résultats" : "Ex. : Filtrer les résultats par période"
                  }
                />
              </label>
              <label className="field">
                Détails
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={
                    type === "bug"
                      ? "Sur quelle page ? Que s'est-il passé ? Depuis quand ?"
                      : "Qu'est-ce que vous voulez pouvoir faire, et pourquoi ?"
                  }
                />
              </label>
              <div className="field">
                Impact pour vous
                <div className="impact">
                  {IMPACTS.map((i) => (
                    <button key={i.k} type="button" className={impact === i.k ? "on" : ""} onClick={() => setImpact(i.k)}>
                      <b>{i.t}</b>
                      <span>{i.d}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="field">
                Photos, vidéo, message vocal
                <div style={{ marginTop: 4 }}>
                  <AttBar state={att} />
                  <PendingList state={att} />
                </div>
              </div>
            </div>
          </>
        )}
        {step === 3 && type && (
          <>
            <h1>On récapitule</h1>
            <p className="hint">Vous pourrez compléter dans la discussion ensuite.</p>
            {bar(3)}
            <div className="card tight" style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                <TypeTag type={type} />
                <span className="tag">{impactInfo.t}</span>
              </div>
              <h2 style={{ fontSize: 18, marginBottom: 6 }}>{title}</h2>
              <div className="desc">{description || <span className="hint">Pas de détails.</span>}</div>
              {att.files.length > 0 && (
                <div className="hint" style={{ marginTop: 6 }}>
                  📎 {att.files.length} pièce(s) jointe(s)
                </div>
              )}
            </div>
          </>
        )}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 20, gap: 8 }}>
          <button className="btn ghost" onClick={step === 1 ? onClose : () => setStep(step - 1)}>
            {step === 1 ? "Annuler" : "← Retour"}
          </button>
          {step < 3 ? (
            <button className="btn white" disabled={!canNext} onClick={() => setStep(step + 1)}>
              Continuer →
            </button>
          ) : (
            <button className="btn grad" disabled={busy} onClick={submit}>
              Envoyer la demande
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
