/** Types et utilitaires de l'écran Finances. */
export interface Summary {
  dev_paid: string;
  dev_left: string;
  dev_total: string;
  licence: string;
  licence_months: number;
  licence_monthly: string;
  quotes_paid: string;
  quotes_left: string;
  quotes_count: number;
  pending_quotes: string;
  total: string;
  to_come: string;
  has_cost: boolean;
  cost: string;
  margin: string;
}
export interface Overview {
  current: string;
  has_cost: boolean;
  default_tjm: string;
  months: { month: string; revenue: Record<string, string>; total: string; cost: string; margin: string }[];
  projects: ({ key: string; name: string; client: string; licence_active: boolean } & Summary)[];
  kpis: { licence_monthly: string; dev_to_come: string; cashed: string };
  to_quote: {
    id: number;
    ref: string;
    title: string;
    project: string;
    estimate_days: string;
    billing: string | null;
    potential: string;
  }[];
}
export interface Installment {
  id: number;
  due_on: string;
  amount: string;
  is_paid: boolean;
  paid_on: string | null;
}
export type CostMode = "none" | "people" | "monthly" | "days";
export interface ProjectFinance {
  key: string;
  name: string;
  client: string;
  dev_price: string;
  licence_amount: string;
  licence_start: string | null;
  licence_end: string | null;
  cost_mode: CostMode;
  cost_monthly: string | null;
  cost_days: string | null;
  cost_tjm: string | null;
  cost_month: string | null;
  summary: Summary;
  people_cost: string;
  months: { month: string; revenue: string; cost: string }[];
  installments: Installment[];
  quotes: {
    id: number;
    ticket: { id: number; ref: string; title: string };
    amount_ht: string;
    status: string;
    installments: Installment[];
  }[];
}
export interface StaffRow {
  user: number;
  name: string;
  monthly_salary: string;
  allocations: Record<string, number>;
  total: number;
  warning: string | null;
}

const monthFmt = new Intl.DateTimeFormat("fr-FR", { month: "short", year: "2-digit" });
/** « 2026-09 » → « sept. 26 ». */
export const fmtM = (m: string) => monthFmt.format(new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)) - 1, 1));
export const num = (v: string | number | null | undefined) => Number(v ?? 0);
