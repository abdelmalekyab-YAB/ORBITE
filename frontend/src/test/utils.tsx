import { render } from "@testing-library/react";
import { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { UIProvider } from "../components/UIContext";
import type { Me, Ticket, TicketDetail } from "../lib/types";

export const julie: Me = {
  id: 4,
  email: "julie@wws.fr",
  name: "Julie Martin",
  first_name: "Julie",
  initials: "JM",
  job: "client",
  organization: "WWS",
  organization_kind: "client",
  is_digitalia: false,
  is_orbit_admin: false,
  projects: [{ key: "SCV", name: "Smart CV", client: "WWS" }],
};

export const STEPS = [
  "Reçue",
  "Proposition à valider",
  "Planifiée",
  "En développement",
  "Validation interne",
  "À tester",
  "Livrée",
];

export function makeTicket(over: Partial<TicketDetail> = {}): TicketDetail {
  return {
    id: 10,
    ref: "SCV-10",
    number: 10,
    project: "SCV",
    project_name: "Smart CV",
    type: "evolution",
    title: "Filtre par date",
    status: "test",
    status_label: "Test client",
    client_label: "À tester",
    ball: "client",
    is_closed: false,
    is_late: false,
    priority: "normal",
    origin: "client",
    author: { id: 4, name: "Julie Martin", initials: "JM", job: "client" },
    assignee: null,
    milestone: null,
    due_on: null,
    billing: null,
    created_at: "2026-09-29T15:55:00Z",
    updated_at: "2026-09-29T15:55:00Z",
    closed_at: null,
    description: "",
    attachments: [],
    comments: [],
    allowed_transitions: ["termine", "cours"],
    children: [],
    quote: null,
    quote_detail: null,
    ...over,
  };
}

type Handler = (init: RequestInit) => unknown;
/** Remplace fetch : `routes` associe "METHODE /chemin" (sans /api/v1) à une réponse ou une fonction. */
export function mockApi(routes: Record<string, unknown | Handler>) {
  const calls: { method: string; path: string; body: RequestInit["body"] }[] = [];
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.replace("/api/v1", "");
    calls.push({ method, path, body: init.body });
    const key = Object.keys(routes).find((k) => k === `${method} ${path}` || k === `${method} ${path.split("?")[0]}`);
    if (!key) return new Response(JSON.stringify({ detail: "not mocked" }), { status: 404 });
    const value = routes[key];
    const data = typeof value === "function" ? (value as Handler)(init) : value;
    if (data instanceof Response) return data;
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

export function renderApp(ui: ReactNode, route = "/") {
  localStorage.setItem("orbit.access", "token");
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <UIProvider>{ui}</UIProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

export const asTicket = (t: TicketDetail): Ticket => t;

/** Rend `children` une fois l'utilisateur chargé (les composants des espaces supposent `me`). */
export function WhenLoggedIn({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  return me ? <>{children}</> : null;
}
