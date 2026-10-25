import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import ExportButton from "../components/ExportButton";
import Kanban from "../components/Kanban";
import TicketDrawer from "../components/TicketDrawer";
import type { Me } from "../lib/types";
import Access from "../pages/dig/Access";
import { julie, makeTicket, mockApi, renderApp, STEPS, WhenLoggedIn } from "./utils";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

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

test("export CSV : jeton dans l'en-tête, jamais dans l'URL", async () => {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
    url.endsWith("/me")
      ? new Response(JSON.stringify(julie))
      : url.includes("/workflow")
        ? new Response(JSON.stringify({ statuses: [], steps: STEPS }))
        : new Response("Référence;Titre\n", { headers: { "Content-Type": "text/csv" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  renderApp(<ExportButton path="/tickets/export.csv" filename="mes-demandes.csv" />);
  fireEvent.click(screen.getByText("⬇ Exporter CSV"));
  await waitFor(() => expect(click).toHaveBeenCalled());
  const call = fetchMock.mock.calls.find(([u]) => String(u).includes("export.csv"))!;
  expect(call[0]).toBe("/api/v1/tickets/export.csv");
  expect((call[1] as RequestInit).headers).toEqual({ Authorization: "Bearer token" });
});

test("RGPD : suppression d'un compte après confirmation", async () => {
  const calls = mockApi({
    "GET /me": admin,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /projects": [],
    "GET /organizations": [],
    "GET /users": [
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
    ],
    "DELETE /users/3": new Response(null, { status: 204 }),
  });
  const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
  renderApp(
    <WhenLoggedIn>
      <Access />
    </WhenLoggedIn>,
  );
  const row = (await screen.findByText("sara@digitalia.io")).closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByText("Supprimer"));
  expect(calls.some((c) => c.method === "DELETE")).toBe(false); // annulé
  fireEvent.click(within(row).getByText("Supprimer"));
  await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/users/3")).toBe(true));
  expect(confirm).toHaveBeenCalledTimes(2);
  const self = screen.getByText("admin@digitalia.io").closest("tr") as HTMLElement;
  expect(within(self).queryByText("Supprimer")).toBeNull(); // pas son propre compte
});

test("kanban : les cartes s'ouvrent au clavier (accessibilité)", async () => {
  const card = makeTicket({ id: 2, ref: "SCV-2", title: "Erreur 500", status: "cours", ball: "digitalia" });
  const calls = mockApi({
    "GET /me": admin,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /projects": [],
    "GET /tickets/board": {
      columns: [{ key: "cours", label: "En cours", ball: "digitalia", statuses: ["cours"], cards: [card] }],
    },
    "GET /tickets/2": card,
    "GET /tickets/2/events": [],
  });
  renderApp(
    <WhenLoggedIn>
      <Kanban members={[]} />
      <TicketDrawer />
    </WhenLoggedIn>,
  );
  const el = await screen.findByRole("button", { name: "SCV-2 Erreur 500" });
  expect(el.getAttribute("tabindex")).toBe("0");
  fireEvent.keyDown(el, { key: "Enter" });
  await waitFor(() => expect(calls.some((c) => c.path === "/tickets/2")).toBe(true)); // la fiche s'ouvre
  expect(await screen.findByRole("heading", { name: "Erreur 500" })).toBeTruthy();
});
