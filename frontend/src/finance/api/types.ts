/** Types du module Finance — miroir des réponses de l'API Django (backend/finance/views.py). */

export type BillingType = "fixed" | "quote";
export type ProfileStatus = "validated" | "proposal";
export type InvoiceStatus = "planned" | "issued";
export type InvoiceKind = "invoice" | "deposit" | "forecast_7421";
export type PaymentStatus = "pending" | "late" | "paid";
/** R15 : état calculé côté serveur */
export type PayState = "paid" | "late" | "due" | "wait";
export type Month = `${number}-${string}`; // "YYYY-MM"

export interface Client {
  id: string;
  name: string;
}

export interface ProjectRef {
  id: string;
  name: string;
  client_id: string;
  billing_type: BillingType;
  status: ProfileStatus;
  monthly_amount: string | null;
  quote_amount: string | null;
  start_month: Month;
  note: string;
}

export interface ProjectDocument {
  id: number;
  kind: string;
  name: string;
  url: string;
}

export interface BillingProfile {
  id: number;
  project: number;
  project_name: string;
  client_id: string;
  client_name: string;
  billing_type: BillingType;
  monthly_amount: string;
  quote_amount: string | null;
  cost: string;
  start_month: Month;
  end_month: Month | "";
  status: ProfileStatus;
  note: string;
  documents: ProjectDocument[];
  updated_at: string;
}

export interface Invoice {
  id: number;
  project: number;
  service_month: Month;
  amount: string;
  label: string;
  kind: InvoiceKind;
  status: InvoiceStatus;
  invoice_number: string;
  po_number: string;
  issued_on: string | null;
  document_url: string | null;
  document_name: string;
  due_date: string | null;
  payment_status: PaymentStatus;
  paid_on: string | null;
  zoho_invoice_id: string;
  updated_at: string;
}

export interface FixedOccurrence {
  id: number;
  project: number;
  month: Month;
  override_amount: string | null;
  billed_marked: boolean;
  document_url: string | null;
  document_name: string;
  due_date: string | null;
  payment_status: PaymentStatus;
  paid_on: string | null;
}

export interface Expense {
  id: number;
  date: string;
  supplier: string;
  category: string;
  label: string;
  project: number | null;
  amount_ht: string;
  vat: string;
  receipt_url: string | null;
  receipt_name: string;
  created_at: string;
}

/** Une facture émise (ou un fixe facturé) — base des encaissements */
export interface BilledItem {
  ref: string;
  project: ProjectRef;
  month: Month;
  amount: string;
  label: string;
  due_date: string | null;
  payment_status: PaymentStatus;
  paid_on: string | null;
  pay_state: PayState;
  has_document: boolean;
  document_name: string;
}

/** À facturer ce mois (R11) */
export interface DueItem {
  key: string;
  project: ProjectRef;
  amount: string;
  label: string;
  overdue_from: Month | null;
}

export interface RemainingRow {
  project: ProjectRef;
  remaining: string;
  billed: string;
  total: string;
  planned: string;
  unplanned: string;
  kind: BillingType;
}
export interface ProposalRow {
  project: ProjectRef;
  value: string;
  waiting_months: number;
}
export interface RankingRow {
  project: ProjectRef;
  revenue: string;
  cost: string;
  margin: string;
}

export interface CashSummary {
  expected_by_month_end: string;
  total: string;
  late_total: string;
  this_month_total: string;
  no_due_total: string;
  later_total: string;
  late: BilledItem[];
  this_month: BilledItem[];
  no_due: BilledItem[];
  later_by_month: Record<Month, BilledItem[]>;
}

export interface Dashboard {
  as_of: string;
  month: Month;
  month_revenue: string;
  month_fixed: string;
  month_quote: string;
  prev_month_revenue: string;
  ytd: string;
  mrr: string;
  to_bill_total: string;
  to_bill: DueItem[];
  billed_this_month_total: string;
  billed_this_month: BilledItem[];
  cash: CashSummary;
  remaining: RemainingRow[];
  proposals: ProposalRow[];
  ranking_12: RankingRow[];
  chart_12: Array<{ month: Month } & Record<string, string>>;
  clients: Client[];
}

export interface MonthRow {
  project: ProjectRef;
  fixed: null | {
    amount: string;
    adjusted: boolean;
    billed: boolean;
    is_current: boolean;
    future: boolean;
    pay_state: PayState | null;
    due_date: string | null;
    paid_on: string | null;
    has_document: boolean;
    document_name: string;
  };
  invoices: Array<{
    id: number;
    amount: string;
    label: string;
    kind: InvoiceKind;
    status: InvoiceStatus;
    pending: boolean;
    pay_state: PayState | null;
    due_date: string | null;
    paid_on: string | null;
    has_document: boolean;
    document_name: string;
  }>;
  total: string;
}
export interface MonthView {
  month: Month;
  rows: MonthRow[];
  total: string;
  to_bill: string;
  current_month: Month;
}

export interface Upcoming {
  remaining: RemainingRow[];
  proposals: ProposalRow[];
  forecast: Array<{ month: Month; fixed: string; planned: string }>;
  planned: Array<{ id: number; project: ProjectRef; service_month: Month; amount: string; label: string; due_now: boolean }>;
}

export interface Recap {
  months: Month[];
  matrix: Record<string, Record<Month, string>>;
  clients: Client[];
  detail: Array<{
    month: Month;
    revenue: string;
    clients: Array<{
      client: Client;
      revenue: string;
      projects: Array<{ project: ProjectRef; revenue: string; lines: string[] }>;
    }>;
  }>;
}

export interface ProjectSheet {
  profile: BillingProfile;
  first_billed_month: Month;
  billed: string;
  remaining: string | null;
  planned: string;
  cost: string;
  margin: string | null;
  rows: Array<{
    month: Month;
    fixed: string;
    fixed_billed: boolean | null;
    to_bill: boolean;
    future: boolean;
    total: string;
    invoices: Array<{
      id: number;
      amount: string;
      label: string;
      kind: InvoiceKind;
      pending: boolean;
      pay_state: PayState | null;
      has_document: boolean;
    }>;
  }>;
}

export interface PaymentUpdate {
  payment_status: PaymentStatus;
  due_date?: string | null;
  paid_on?: string | null;
}
