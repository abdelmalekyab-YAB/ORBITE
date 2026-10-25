import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { Me } from "../lib/types";
import Access from "../pages/dig/Access";
import { julie, mockApi, renderApp, STEPS, WhenLoggedIn } from "./utils";

afterEach(() => vi.unstubAllGlobals());

const admin: Me = {
  ...julie,
  id: 1,
  email: "direction@digitalia-ltd.com",
  name: "Direction Digitalia",
  first_name: "Direction",
  job: "admin",
  organization: "Digitalia",
  organization_kind: "digitalia",
  is_digitalia: true,
  is_orbit_admin: true,
  projects: [],
};

test("base neuve : premier client puis premier projet (le client créé est bien sélectionné)", async () => {
  let orgs: unknown[] = [];
  const calls = mockApi({
    "GET /me": admin,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /projects": [],
    "GET /users": [
      {
        id: 1,
        email: admin.email,
        name: admin.name,
        initials: "DD",
        job: "admin",
        organization: null,
        is_active: true,
        status: "active",
        projects: [],
      },
    ],
    "GET /organizations": () => orgs,
    "POST /organizations": () => {
      orgs = [{ id: 7, name: "Client Réel", is_active: true, users: [], projects: [] }];
      return orgs[0];
    },
    "POST /projects": { key: "CLR" },
  });
  renderApp(
    <WhenLoggedIn>
      <Access />
    </WhenLoggedIn>,
  );
  fireEvent.change(await screen.findByPlaceholderText("Ex. : Atlas Énergie"), { target: { value: "Client Réel" } });
  fireEvent.change(screen.getByPlaceholderText("contact@client.fr"), { target: { value: "contact@client-reel.fr" } });
  fireEvent.click(screen.getByText("＋ Créer le client"));
  expect(await screen.findByText("Client Réel", { selector: "option" })).toBeTruthy();

  fireEvent.change(screen.getByPlaceholderText("Ex. : Portail RH"), { target: { value: "Portail client" } });
  fireEvent.change(screen.getByPlaceholderText("PRH"), { target: { value: "clr" } });
  const create = screen.getByText("＋ Créer le projet") as HTMLButtonElement;
  expect(create.disabled).toBe(false);
  fireEvent.click(create);
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/projects")).toBe(true));
  expect(JSON.parse(calls.find((c) => c.path === "/projects" && c.method === "POST")!.body as string)).toMatchObject({
    key: "CLR",
    name: "Portail client",
    client: 7,
    lead: 1,
  });
});
