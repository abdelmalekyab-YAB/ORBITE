import type { Month } from "../api/types";

export const eur = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
export const eur2 = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});
export const n = (v: string | number | null | undefined) => (v == null ? 0 : Number(v));

export const monthLabel = (m: Month | string, short = false) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleDateString(
    "fr-FR",
    short ? { month: "short", year: "2-digit" } : { month: "long", year: "numeric" },
  );
};
export const addMonths = (m: Month, k: number): Month => {
  const [y, mo] = m.split("-").map(Number);
  const d = new Date(y, mo - 1 + k, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}` as Month;
};
export const currentMonth = (): Month => new Date().toISOString().slice(0, 7) as Month;
export const fmtDate = (d: string | null | undefined, withYear = true) =>
  d
    ? d
        .split("-")
        .reverse()
        .slice(0, withYear ? 3 : 2)
        .join("/")
    : "";

/** Couleur par client (palette DIGITALIA) — index stable sur l'ordre de la liste clients. */
export const PALETTE = [
  "#6A3FBF",
  "#24969A",
  "#B45CD0",
  "#3E7BD9",
  "#E0912F",
  "#2FB884",
  "#C2412D",
  "#8E7BE0",
  "#6B7A99",
  "#1F6F75",
];
export const clientColor = (clients: { id: string }[], id: string) =>
  PALETTE[
    Math.max(
      0,
      clients.findIndex((c) => c.id === id),
    ) % PALETTE.length
  ];
