/** Client HTTP du module Finance : passe par `api()` d'Orbit (JWT, rafraîchissement du jeton). */
import { ApiError, api, download } from "../../lib/api";
import type * as T from "./types";

const BASE = "/billing";

const http = <R>(path: string, init: RequestInit = {}): Promise<R> => api<R>(BASE + path, init);
export { ApiError };

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const form = (data: Record<string, string | Blob>): RequestInit => {
  const fd = new FormData();
  Object.entries(data).forEach(([k, v]) => fd.append(k, v));
  return { method: "POST", body: fd };
};

export const finance = {
  // Lectures agrégées
  dashboard: () => http<T.Dashboard>("/dashboard/"),
  month: (m: T.Month) => http<T.MonthView>(`/month/${m}/`),
  upcoming: (horizon = 6) => http<T.Upcoming>(`/upcoming/?horizon=${horizon}`),
  recap: (period: "year" | "12" | "all") => http<T.Recap>(`/recap/?period=${period}`),

  // Profils de facturation (projets)
  profiles: () => http<T.BillingProfile[]>("/profiles/"),
  createProfile: (data: Partial<T.BillingProfile>) => http<T.BillingProfile>("/profiles/", json(data)),
  updateProfile: (id: number, data: Partial<T.BillingProfile>) =>
    http<T.BillingProfile>(`/profiles/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteProfile: (id: number) => http<void>(`/profiles/${id}/`, { method: "DELETE" }),
  sheet: (id: number) => http<T.ProjectSheet>(`/profiles/${id}/sheet/`),
  addProjectDocument: (id: number, file: File, kind: string) =>
    http<T.BillingProfile>(`/profiles/${id}/documents/`, form({ file, kind })),

  // Factures
  invoices: (params: Partial<{ project: number; service_month: T.Month; status: T.InvoiceStatus }> = {}) =>
    http<T.Invoice[]>("/invoices/?" + new URLSearchParams(params as Record<string, string>)),
  createInvoice: (data: Partial<T.Invoice>) => http<T.Invoice>("/invoices/", json(data)),
  updateInvoice: (id: number, data: Partial<T.Invoice>) =>
    http<T.Invoice>(`/invoices/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteInvoice: (id: number) => http<void>(`/invoices/${id}/`, { method: "DELETE" }),
  markIssued: (id: number) => http<T.Invoice>(`/invoices/${id}/mark_issued/`, { method: "POST" }),
  markPlanned: (id: number) => http<T.Invoice>(`/invoices/${id}/mark_planned/`, { method: "POST" }),
  invoicePayment: (id: number, data: T.PaymentUpdate) => http<T.Invoice>(`/invoices/${id}/payment/`, json(data)),
  invoiceDocument: (id: number, file: File) => http<T.Invoice>(`/invoices/${id}/document/`, form({ file })),
  /** Met à jour la ligne « CA prévu 74+21 » du mois — ne crée jamais de doublon (409 si déjà émise). */
  forecast7421: (project: number, service_month: T.Month, amount: number) =>
    http<T.Invoice>("/invoices/forecast_7421/", json({ project, service_month, amount })),

  // Occurrences fixes (projet × mois)
  fixedAdjust: (project: number, month: T.Month, amount: number | null) =>
    http<T.FixedOccurrence>(
      "/fixed/adjust/",
      json(amount === null ? { project, month, reset: true } : { project, month, amount }),
    ),
  fixedMark: (project: number, month: T.Month, billed: boolean) =>
    http<T.FixedOccurrence>("/fixed/mark/", json({ project, month, billed })),
  fixedPayment: (project: number, month: T.Month, data: T.PaymentUpdate) =>
    http<T.FixedOccurrence>("/fixed/payment/", json({ project, month, ...data })),
  fixedDocument: (project: number, month: T.Month, file: File) =>
    http<T.FixedOccurrence>("/fixed/document/", form({ project: String(project), month, file })),

  // Dépenses
  expenses: (month?: T.Month) => http<T.Expense[]>("/expenses/" + (month ? `?month=${month}` : "")),
  createExpense: (data: FormData) => http<T.Expense>("/expenses/", { method: "POST", body: data }),
  deleteExpense: (id: number) => http<void>(`/expenses/${id}/`, { method: "DELETE" }),
  expenseReceipt: (id: number, file: File) => http<T.Expense>(`/expenses/${id}/receipt/`, form({ file })),

  // Exports (URLs à ouvrir dans un <a download> ; `kind`, pas `format`)
  /** Téléchargements authentifiés (un simple lien n'enverrait pas le jeton). */
  downloadAccountingExport: (p: { from: T.Month; to: T.Month; client?: string; expenses?: boolean; kind: "xlsx" | "zip" }) =>
    download(
      `${BASE}/export/accounting/?` +
        +new URLSearchParams({
          from: p.from,
          to: p.to,
          kind: p.kind,
          expenses: p.expenses === false ? "0" : "1",
          ...(p.client ? { client: p.client } : {}),
        }),
      `digitalia-comptabilite-${p.from}-${p.to}.${p.kind}`,
    ),
  downloadCeoPdf: () => download(`${BASE}/export/ceo.pdf`, "digitalia-synthese.pdf"),
  orbitProjects: () => http<Array<{ id: number; name: string; client_id: string; client_name: string }>>("/orbit-projects/"),

  // Zoho — lecture seule
  zohoSync: () =>
    http<{
      ok: boolean;
      updated: number;
      issues: Array<{ invoice_number: string; issue: string; detail: string }>;
      error: string;
    }>("/zoho/sync/", { method: "POST" }),
};
