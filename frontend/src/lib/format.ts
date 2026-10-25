import type { Priority, Ticket, TicketType } from "./types";

export const TYPE_LABEL: Record<TicketType, string> = {
  bug: "Bug / anomalie",
  evolution: "Demande d'évolution",
  feature: "Nouvelle fonctionnalité",
  question: "Question",
  support: "Demande de support",
  internal: "Tâche interne",
};
export const TYPE_TAG: Record<TicketType, string> = {
  bug: "bug",
  evolution: "evo",
  feature: "evo",
  question: "q",
  support: "q",
  internal: "int",
};
export const PRIORITY_LABEL: Record<Priority, string> = { low: "Basse", normal: "Normale", high: "Haute", critical: "Critique" };

const dateFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const dateTimeFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export const fmtD = (d: string | null | undefined) => (d ? dateFmt.format(new Date(d)) : "—");
export const fmtDT = (d: string | null | undefined) => (d ? dateTimeFmt.format(new Date(d)) : "—");

/** « La balle est chez qui » vue par l'utilisateur courant. */
export type BallView = "you" | "dig" | "done";
export const ballOf = (t: Pick<Ticket, "is_closed" | "ball">): BallView =>
  t.is_closed ? "done" : t.ball === "client" ? "you" : "dig";

/** Phrase d'étape affichée sous le titre (reprise de la maquette). */
export function stepLabel(t: Ticket): string {
  switch (t.status) {
    case "attente":
      return "En développement — une précision vous est demandée";
    case "refuse":
      return "Refusée";
    case "annule":
      return "Annulée";
    case "nouveau":
      return "Reçue — en attente de qualification";
    case "analyser":
      return "Reçue — en cours d'analyse";
    case "devis":
      return "Proposition commerciale à valider — le développement démarre après votre accord";
    case "testint":
      return "Validation interne — l'équipe Digitalia vérifie avant de vous l'envoyer";
    default:
      return t.client_label;
  }
}

export const plural = (n: number, word: string) => `${n} ${word}${n > 1 ? "s" : ""}`;

const euroFmt = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
/** Montant en euros, arrondi à l'euro comme dans la maquette (« 3 600 € »). */
export const fmtE = (n: number | string | null | undefined) => euroFmt.format(Number(n ?? 0));
export const PARTS_LABEL: Record<number, string> = {
  1: "en une fois",
  2: "50 % à la commande, 50 % à la livraison",
  3: "30 % / 40 % / 30 %",
};
