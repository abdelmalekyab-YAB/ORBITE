import type { Health, Ticket } from "./types";

/** Règle 23, appliquée à une liste déjà filtrée (miroir du calcul serveur, pour le mode « tous mes projets »). */
export function healthOf(list: Ticket[]): { health: Health; reason: string } {
  const open = list.filter((t) => !t.is_closed);
  const late = open.filter((t) => t.is_late).length;
  const fresh = open.filter((t) => t.status === "nouveau").length;
  const waiting = open.filter((t) => t.status === "attente").length;
  if (late) return { health: "late", reason: `${late} demande${late > 1 ? "s" : ""} au-delà de la date prévue` };
  if (fresh >= 2 || waiting) {
    const parts = [fresh >= 2 ? `${fresh} nouvelles à qualifier` : "", waiting ? `${waiting} en attente du client` : ""];
    return { health: "watch", reason: parts.filter(Boolean).join(" · ") };
  }
  return { health: "ok", reason: "Aucun retard, rien de bloqué" };
}

export const progressOf = (list: Ticket[]) =>
  list.length ? Math.round((list.filter((t) => t.client_label === "Livrée").length / list.length) * 100) : 0;
