import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import NotificationBell from "../components/NotificationBell";
import type { Me } from "../lib/types";
import Access from "../pages/dig/Access";
import Settings from "../pages/dig/Settings";
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
const status = (key: string, label: string, client_label: string, next: string[], extra = {}) => ({
  key,
  label,
  client_label,
  ball: "digitalia",
  is_closed: false,
  is_terminal_ok: false,
  order: 0,
  color: "",
  next,
  is_system: false,
  ...extra,
});
const WORKFLOW = {
  steps: STEPS,
  statuses: [
    status("nouveau", "Nouveau", "Reçue", ["cours"], { is_system: true }),
    status("cours", "En cours", "En développement", ["termine"]),
    status("termine", "Terminé", "Livrée", ["cours"], { is_closed: true, is_terminal_ok: true, ball: "none", is_system: true }),
  ],
};

test("invitation : création du mot de passe puis connexion", async () => {
  const calls = mockApi({
    "POST /auth/invite/accept": { access: "a", refresh: "r", me: julie },
    "GET /workflow": WORKFLOW,
    "GET /tickets": { results: [] },
    "GET /projects/SCV": { milestones: [] },
    "GET /activity": [],
    "GET /notifications": { unread: 0, results: [] },
  });
  render(
    <MemoryRouter initialEntries={["/invitation?uid=MTA&token=abc-123"]}>
      <App />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText("Mot de passe"), { target: { value: "Orbit-2026!" } });
  fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), { target: { value: "Autre-2026!" } });
  fireEvent.click(screen.getByText("Créer mon mot de passe →"));
  expect(await screen.findByText("Les deux mots de passe ne correspondent pas.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), { target: { value: "Orbit-2026!" } });
  fireEvent.click(screen.getByText("Créer mon mot de passe →"));
  await waitFor(() => expect(calls.some((c) => c.path === "/auth/invite/accept")).toBe(true));
  expect(JSON.parse(calls.find((c) => c.path === "/auth/invite/accept")!.body as string)).toEqual({
    uid: "MTA",
    token: "abc-123",
    password: "Orbit-2026!",
  });
  expect(await screen.findByText("Mes demandes")).toBeTruthy(); // connecté, espace client
  expect(localStorage.getItem("orbit.access")).toBe("a");
});

test("mot de passe oublié : message neutre", async () => {
  mockApi({ "POST /auth/password/forgot": { detail: "Si un compte existe pour cette adresse, un e-mail vient d'être envoyé." } });
  render(
    <MemoryRouter initialEntries={["/mot-de-passe-oublie"]}>
      <App />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText("E-mail"), { target: { value: "julie@wws.fr" } });
  fireEvent.click(screen.getByText("Recevoir le lien →"));
  expect(await screen.findByText(/Si un compte existe/)).toBeTruthy();
});

const TEAM = [
  {
    id: 1,
    email: "admin@digitalia.io",
    name: "Yasmina A.",
    initials: "YA",
    job: "admin",
    organization: null,
    is_active: true,
    status: "active",
    projects: [],
  },
  {
    id: 3,
    email: "sara@digitalia.io",
    name: "Sara Dev",
    initials: "SD",
    job: "dev",
    organization: null,
    is_active: true,
    status: "active",
    projects: [],
  },
];
const ORGS = [
  {
    id: 2,
    name: "WWS",
    is_active: true,
    projects: [
      { key: "SCV", name: "Smart CV", is_archived: false },
      { key: "CHK", name: "Checklists", is_archived: false },
    ],
    users: [
      {
        id: 4,
        email: "julie@wws.fr",
        name: "Julie Martin",
        initials: "JM",
        job: "client",
        organization: { id: 2, name: "WWS", kind: "client" },
        is_active: true,
        status: "active",
        projects: ["SCV", "CHK"],
      },
    ],
  },
];

function accessApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    "GET /me": admin,
    "GET /workflow": WORKFLOW,
    "GET /users": TEAM,
    "GET /organizations": ORGS,
    "GET /projects": [],
    ...extra,
  });
}

test("accès : retirer un projet à un utilisateur client", async () => {
  const calls = accessApi({ "PUT /users/4/project-access": ORGS[0].users[0] });
  renderApp(
    <WhenLoggedIn>
      <Access />
    </WhenLoggedIn>,
  );
  const row = (await screen.findByText("Julie Martin")).closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByText("Checklists"));
  await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  expect(JSON.parse(calls.find((c) => c.method === "PUT")!.body as string)).toEqual({ projects: ["SCV"] });
});

test("accès : inviter un membre de l'équipe", async () => {
  const calls = accessApi({ "POST /users": { ...TEAM[1], id: 9 } });
  renderApp(
    <WhenLoggedIn>
      <Access />
    </WhenLoggedIn>,
  );
  fireEvent.change(await screen.findByPlaceholderText("prenom@digitalia.io"), { target: { value: "lea@digitalia.io" } });
  fireEvent.change(screen.getAllByPlaceholderText("Prénom Nom")[0], { target: { value: "Léa Dev" } });
  fireEvent.click(screen.getByText("＋ Inviter"));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/users")).toBe(true));
  expect(JSON.parse(calls.find((c) => c.path === "/users" && c.method === "POST")!.body as string)).toEqual({
    name: "Léa Dev",
    email: "lea@digitalia.io",
    job: "dev",
  });
  expect(screen.getByLabelText("Rôle de Yasmina A.")).toHaveProperty("disabled", true); // pas son propre rôle
});

test("réglages : renommer une étape client met à jour la piste et enregistre", async () => {
  const calls = mockApi({
    "GET /me": admin,
    "GET /workflow": WORKFLOW,
    "PUT /workflow": WORKFLOW,
    "GET /settings/notifications": { client_planned: true, client_reminder: false, reminder_days: 3 },
  });
  renderApp(
    <WhenLoggedIn>
      <Settings />
    </WhenLoggedIn>,
  );
  fireEvent.change(await screen.findByLabelText("Étape client cours"), { target: { value: "En fabrication" } });
  expect(within(screen.getByTestId("client-track")).getByText("En fabrication")).toBeTruthy();
  fireEvent.click(screen.getByLabelText("Supprimer En cours")); // statut non système
  expect(screen.queryByLabelText("Supprimer Nouveau")).toBeNull(); // statut système
  fireEvent.click(screen.getByText("＋ Ajouter un statut"));
  fireEvent.click(screen.getByText("✓ Enregistrer le workflow"));
  await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.path === "/workflow")).toBe(true));
  const sent = JSON.parse(calls.find((c) => c.method === "PUT")!.body as string).statuses;
  expect(sent.map((s: { key: string }) => s.key)).toEqual(["nouveau", "statut1", "termine"]);
  expect(sent[0].next).toEqual([]); // la transition vers le statut supprimé est retirée
});

test("réglages : activer le rappel client", async () => {
  const calls = mockApi({
    "GET /me": admin,
    "GET /workflow": WORKFLOW,
    "GET /settings/notifications": { client_planned: true, client_reminder: false, reminder_days: 3 },
    "PUT /settings/notifications": { client_planned: true, client_reminder: true, reminder_days: 3 },
  });
  renderApp(
    <WhenLoggedIn>
      <Settings />
    </WhenLoggedIn>,
  );
  fireEvent.click(await screen.findByLabelText(/Rappel quand la balle est chez lui/));
  await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  expect(JSON.parse(calls.find((c) => c.method === "PUT")!.body as string)).toEqual({ client_reminder: true });
});

test("cloche : non lues, ouverture d'une notification", async () => {
  const calls = mockApi({
    "GET /me": julie,
    "GET /workflow": WORKFLOW,
    "POST /notifications/7/read": { unread: 0 },
    "GET /notifications": {
      unread: 1,
      results: [
        {
          id: 7,
          kind: "ready_to_test",
          title: "SCV-10 est prête à tester",
          ticket: { id: 10, ref: "SCV-10", title: "Filtre par date" },
          created_at: "2026-09-29T17:00:00Z",
          read_at: null,
        },
      ],
    },
  });
  renderApp(
    <WhenLoggedIn>
      <NotificationBell />
    </WhenLoggedIn>,
  );
  fireEvent.click(await screen.findByLabelText("Notifications (1 non lues)"));
  fireEvent.click(screen.getByText(/SCV-10 est prête à tester/));
  await waitFor(() => expect(calls.some((c) => c.path === "/notifications/7/read")).toBe(true));
});

test("onglets par rôle : un développeur n'a ni Triage, ni Réglages, ni Accès (règle 3)", async () => {
  const dev: Me = { ...admin, job: "dev", is_orbit_admin: false };
  mockApi({
    "GET /me": dev,
    "GET /workflow": WORKFLOW,
    "GET /cockpit": { projects: [], to_handle: [], workload: [], activity: [] },
    "GET /team": { members: [], unassigned: 0 },
    "GET /notifications": { unread: 0, results: [] },
  });
  localStorage.setItem("orbit.access", "token");
  render(
    <MemoryRouter initialEntries={["/dig/reglages"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Cockpit", { selector: "h1" })).toBeTruthy();
  for (const tab of ["Triage", "Réglages", "Accès", "Finances"]) expect(screen.queryByText(tab)).toBeNull();
});
