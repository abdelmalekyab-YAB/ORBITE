import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import ProjectFinanceTab from "../components/ProjectFinanceTab";
import type { Overview, ProjectFinance, StaffRow, Summary } from "../lib/finance";
import type { Me } from "../lib/types";
import Finance from "../pages/dig/Finance";
import { julie, mockApi, renderApp, STEPS, WhenLoggedIn } from "./utils";

afterEach(() => vi.unstubAllGlobals());

const admin: Me = {
  ...julie,
  id: 1,
  email: "admin@digitalia.io",
  name: "Yasmina A.",
  first_name: "Yasmina",
  job: "admin",
  organization: "Digitalia",
  organization_kind: "digitalia",
  is_digitalia: true,
  is_orbit_admin: true,
  projects: [],
};
const summary: Summary = {
  dev_paid: "12600.00",
  dev_left: "5400.00",
  dev_total: "18000.00",
  licence: "1780.00",
  licence_months: 2,
  licence_monthly: "890.00",
  quotes_paid: "0.00",
  quotes_left: "0.00",
  quotes_count: 0,
  pending_quotes: "3600.00",
  total: "14380.00",
  to_come: "5400.00",
  has_cost: true,
  cost: "13800.00",
  margin: "580.00",
};
const overview: Overview = {
  current: "2026-09",
  has_cost: true,
  default_tjm: "450.00",
  months: [
    { month: "2026-09", revenue: { SCV: "890.00" }, total: "890.00", cost: "2760.00", margin: "-1870.00" },
    { month: "2026-10", revenue: { SCV: "6290.00" }, total: "6290.00", cost: "2760.00", margin: "3530.00" },
  ],
  projects: [{ key: "SCV", name: "Smart CV", client: "WWS", licence_active: true, ...summary }],
  kpis: { licence_monthly: "890.00", dev_to_come: "5400.00", cashed: "14380.00" },
  to_quote: [
    {
      id: 9,
      ref: "SCV-9",
      title: "Nouvelle page statistiques",
      project: "Smart CV",
      estimate_days: "2.5",
      billing: "quote",
      potential: "1125.00",
    },
  ],
};
const projectFin: ProjectFinance = {
  key: "SCV",
  name: "Smart CV",
  client: "WWS",
  dev_price: "18000.00",
  licence_amount: "890.00",
  licence_start: "2026-08",
  licence_end: null,
  cost_mode: "people",
  cost_monthly: null,
  cost_days: null,
  cost_tjm: null,
  cost_month: null,
  summary,
  people_cost: "2760.00",
  months: overview.months.map((m) => ({ month: m.month, revenue: m.total, cost: m.cost })),
  installments: [{ id: 5, due_on: "2026-10-15", amount: "5400.00", is_paid: false, paid_on: null }],
  quotes: [],
};
const staff: StaffRow[] = [
  { user: 3, name: "Sara Dev", monthly_salary: "3600.00", allocations: { SCV: 30 }, total: 30, warning: null },
];

function financeApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    "GET /me": admin,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /finance/overview": overview,
    "GET /finance/projects/SCV": projectFin,
    "GET /finance/staff": staff,
    ...extra,
  });
}

test("écran Finances : KPI du mois, total par projet, changement de mois", async () => {
  financeApi();
  renderApp(
    <WhenLoggedIn>
      <Finance />
    </WhenLoggedIn>,
  );
  expect(await screen.findByText("Recettes sept. 26 · tous projets")).toBeTruthy();
  expect(screen.getAllByText("14 380 €").length).toBeGreaterThan(0);
  expect(screen.getByText(/Marge sept\. 26/)).toBeTruthy();
  fireEvent.click(screen.getAllByText("oct. 26")[0]);
  expect(await screen.findByText("Recettes oct. 26 · tous projets")).toBeTruthy();
  expect(screen.getByText(/Ces estimations n'entrent jamais dans les recettes/)).toBeTruthy();
});

test("affectation > 100 % : enregistrée avec un avertissement (règle 21)", async () => {
  const calls = financeApi({
    "PUT /finance/staff": [{ ...staff[0], allocations: { SCV: 120 }, total: 120, warning: "Affectations supérieures à 100 %." }],
  });
  renderApp(
    <WhenLoggedIn>
      <Finance />
    </WhenLoggedIn>,
  );
  const input = await screen.findByLabelText("Sara Dev Smart CV %");
  fireEvent.change(input, { target: { value: "120" } });
  fireEvent.blur(input);
  await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.path === "/finance/staff")).toBe(true));
  expect(await screen.findByText(/Affectations supérieures à 100 %/)).toBeTruthy();
});

test("onglet Finances du projet : encaisser une échéance", async () => {
  const calls = financeApi({ "PATCH /finance/projects/SCV/installments/5": { ...projectFin.installments[0], is_paid: true } });
  renderApp(
    <WhenLoggedIn>
      <ProjectFinanceTab projectKey="SCV" />
    </WhenLoggedIn>,
  );
  const card = (await screen.findByText("Échéances")).closest(".card") as HTMLElement;
  fireEvent.click(within(card).getByText("À venir"));
  await waitFor(() =>
    expect(calls.some((c) => c.method === "PATCH" && c.path === "/finance/projects/SCV/installments/5")).toBe(true),
  );
  expect(JSON.parse(calls.find((c) => c.method === "PATCH")!.body as string)).toEqual({ is_paid: true });
});

test("l'onglet Finances n'apparaît que pour l'admin (règle 3)", async () => {
  const pm: Me = { ...admin, job: "pm", is_orbit_admin: false };
  mockApi({
    "GET /me": pm,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /cockpit": { projects: [], to_handle: [], workload: [], activity: [] },
    "GET /team": { members: [], unassigned: 0 },
    "GET /triage": [],
  });
  localStorage.setItem("orbit.access", "token");
  render(
    <MemoryRouter initialEntries={["/dig/finances"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Cockpit", { selector: "h1" })).toBeTruthy(); // redirigé
  expect(screen.queryByText("Finances")).toBeNull();
  expect(screen.getByText("Triage")).toBeTruthy();
});
