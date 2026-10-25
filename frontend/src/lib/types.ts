export type Job = "admin" | "pm" | "dev" | "client";
export type Ball = "client" | "digitalia" | "none";
export type TicketType = "bug" | "evolution" | "feature" | "question" | "support" | "internal";
export type Priority = "low" | "normal" | "high" | "critical";

export interface UserMini {
  id: number;
  name: string;
  initials: string;
  job: Job;
}

export interface Me {
  id: number;
  email: string;
  name: string;
  first_name: string;
  initials: string;
  job: Job;
  organization: string | null;
  organization_kind: "digitalia" | "client" | null;
  is_digitalia: boolean;
  is_orbit_admin: boolean;
  projects: { key: string; name: string; client: string }[];
}

export interface Milestone {
  id: number;
  name: string;
  starts_on: string | null;
  ends_on: string | null;
  order: number;
}

export type Health = "ok" | "watch" | "late";
export interface Project {
  key: string;
  name: string;
  description: string;
  client: string;
  lead: UserMini | null;
  is_archived: boolean;
  health: Health;
  reason: string;
  counts: { open: number; client: number; digitalia: number; delivered: number; late: number };
  milestones?: Milestone[];
}

export interface Attachment {
  id: number;
  name: string;
  content_type: string;
  url: string;
  created_at: string;
}

export type CommentKind = "comment" | "refusal" | "quote_refusal" | "reopen" | "ping";
export interface Comment {
  id: number;
  author: UserMini;
  author_is_digitalia: boolean;
  body: string;
  kind: CommentKind;
  attachments: Attachment[];
  created_at: string;
}

export interface Ticket {
  id: number;
  ref: string;
  number: number;
  project: string;
  project_name: string;
  type: TicketType;
  title: string;
  status: string;
  status_label: string;
  client_label: string;
  ball: Ball;
  is_closed: boolean;
  is_late: boolean;
  priority: Priority;
  origin: "client" | "digitalia";
  is_internal?: boolean;
  author: UserMini;
  assignee: UserMini | null;
  milestone: { id: number; name: string } | null;
  due_on: string | null;
  parent?: { id: number; ref: string; title: string } | null;
  billing: "licence" | "quote" | null;
  estimate_days?: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  quote: { amount_ht: string; status: QuoteStatus } | null;
}

export type QuoteStatus = "draft" | "sent" | "accepted" | "refused";
export interface QuoteInstallment {
  id: number;
  due_on: string;
  amount: string;
  is_paid: boolean;
  paid_on: string | null;
}
export interface Quote {
  id: number;
  amount_ht: string;
  parts: 1 | 2 | 3;
  description: string;
  pdf: string | null;
  status: QuoteStatus;
  sent_at: string | null;
  decided_at: string | null;
  decided_by: UserMini | null;
  installments: QuoteInstallment[];
}

export interface TicketDetail extends Ticket {
  description: string;
  attachments: Attachment[];
  comments: Comment[];
  allowed_transitions: string[];
  children: { id: number; ref: string; title: string; status: string; status_label: string }[];
  quote_detail: Quote | null;
}

export interface TicketEvent {
  id: number;
  actor: UserMini | null;
  kind: string;
  from_value: string;
  to_value: string;
  message: string;
  at: string;
}

export interface WorkflowStatus {
  key: string;
  label: string;
  client_label: string;
  ball: Ball;
  is_closed: boolean;
  is_terminal_ok: boolean;
  order: number;
  color: string;
  next: string[];
  is_system: boolean;
}
export interface Workflow {
  statuses: WorkflowStatus[];
  steps: string[];
}

export interface BoardColumn {
  key: string;
  label: string;
  ball: Ball;
  statuses: string[];
  cards: Ticket[];
}

export interface Page<T> {
  next: string | null;
  previous: string | null;
  results: T[];
}
