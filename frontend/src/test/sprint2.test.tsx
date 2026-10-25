import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import Roadmap from "../components/Roadmap";
import TicketDrawer from "../components/TicketDrawer";
import { useUI } from "../components/UIContext";
import type { Me, Quote } from "../lib/types";
import Triage from "../pages/dig/Triage";
import { julie, makeTicket, mockApi, renderApp, STEPS, WhenLoggedIn } from "./utils";

afterEach(() => vi.unstubAllGlobals());

const yanis: Me = {
  ...julie,
  id: 2,
  email: "yanis@digitalia.io",
  name: "Yanis PM",
  first_name: "Yanis",
  job: "pm",
  organization: "Digitalia",
  organization_kind: "digitalia",
  is_digitalia: true,
  projects: [],
};
const QUOTE: Quote = {
  id: 1,
  amount_ht: "3600.00",
  parts: 2,
  description: "Module campagnes.",
  pdf: null,
  status: "sent",
  sent_at: "2026-09-29T16:00:00Z",
  decided_at: null,
  decided_by: null,
  installments: [],
};
const devis = makeTicket({
  id: 3,
  ref: "SCV-3",
  title: "Campagnes de formation",
  status: "devis",
  type: "feature",
  client_label: "Proposition à valider",
  ball: "client",
  allowed_transitions: [],
  quote: { amount_ht: "3600.00", status: "sent" },
  quote_detail: QUOTE,
});

function OpenDrawer({ id }: { id: number }) {
  const { me } = useAuth();
  const { openTicket } = useUI();
  useEffect(() => {
    if (me) openTicket(id);
  }, [me, id, openTicket]);
  return me ? <TicketDrawer /> : null;
}

function drawerApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    "GET /me": julie,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /tickets/3": devis,
    "GET /tickets/3/events": [],
    ...extra,
  });
}

test("le client accepte la proposition", async () => {
  const calls = drawerApi({
    "POST /tickets/3/quote/accept": makeTicket({ ...devis, status: "faire", quote_detail: { ...QUOTE, status: "accepted" } }),
  });
  renderApp(<OpenDrawer id={3} />);
  expect(await screen.findByText("3 600 €", { exact: false })).toBeTruthy();
  fireEvent.click(screen.getByText(/J'accepte la proposition/));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/tickets/3/quote/accept")).toBe(true));
});

test("refuser la proposition exige un motif (règle 17)", async () => {
  const calls = drawerApi({ "POST /tickets/3/quote/refuse": makeTicket({ ...devis, status: "refuse" }) });
  renderApp(<OpenDrawer id={3} />);
  fireEvent.click(await screen.findByText("Refuser"));
  fireEvent.click(screen.getByText("Refuser la proposition"));
  expect(await screen.findByText(/10 caractères minimum/)).toBeTruthy();
  expect(calls.some((c) => c.path.endsWith("/quote/refuse"))).toBe(false);
  fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "Budget déjà engagé cette année." } });
  fireEvent.click(screen.getByText("Refuser la proposition"));
  await waitFor(() => expect(calls.some((c) => c.path === "/tickets/3/quote/refuse")).toBe(true));
  const body = calls.find((c) => c.path === "/tickets/3/quote/refuse")!.body as FormData;
  expect(body.get("reason")).toBe("Budget déjà engagé cette année.");
});

test("triage : une évolution sur devis envoie la proposition", async () => {
  const evo = makeTicket({
    id: 12,
    ref: "SCV-12",
    title: "Export Excel",
    status: "nouveau",
    type: "evolution",
    client_label: "Reçue",
    ball: "digitalia",
    billing: null,
    estimate_days: "4",
  });
  const calls = mockApi({
    "GET /me": yanis,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /triage": [evo],
    "GET /tickets/12": evo,
    "GET /projects/SCV/milestones": [],
    "GET /finance/settings": { default_tjm: "450.00" },
    "POST /tickets/12/triage": { ...evo, status: "devis" },
  });
  renderApp(
    <WhenLoggedIn>
      <Triage members={[{ id: 3, name: "Sara Dev" }]} />
    </WhenLoggedIn>,
  );
  fireEvent.click(await screen.findByText("Sur devis"));
  expect(await screen.findByText(/4 j × 450 € = 1 800 €/)).toBeTruthy();
  fireEvent.click(screen.getByText(/Envoyer la proposition/));
  await waitFor(() => expect(calls.some((c) => c.path === "/tickets/12/triage")).toBe(true));
  const body = calls.find((c) => c.path === "/tickets/12/triage")!.body as FormData;
  expect(body.get("decision")).toBe("devis");
  expect(body.get("billing")).toBe("quote");
  expect(body.get("quote_amount_ht")).toBe("1800");
});

test("triage : planifier une évolution incluse dans la licence", async () => {
  const evo = makeTicket({
    id: 12,
    ref: "SCV-12",
    title: "Export Excel",
    status: "nouveau",
    type: "evolution",
    client_label: "Reçue",
    ball: "digitalia",
    billing: null,
  });
  const calls = mockApi({
    "GET /me": yanis,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /triage": [evo],
    "GET /tickets/12": evo,
    "GET /projects/SCV/milestones": [],
    "POST /tickets/12/triage": { ...evo, status: "faire" },
  });
  renderApp(
    <WhenLoggedIn>
      <Triage members={[]} />
    </WhenLoggedIn>,
  );
  fireEvent.click(await screen.findByText("✓ Planifier"));
  await waitFor(() => expect(calls.some((c) => c.path === "/tickets/12/triage")).toBe(true));
  const body = calls.find((c) => c.path === "/tickets/12/triage")!.body as FormData;
  expect([body.get("decision"), body.get("billing")]).toEqual(["faire", "licence"]);
});

test("feuille de route : versions, progression et contenu", async () => {
  mockApi({
    "GET /me": julie,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /projects/SCV/milestones": [
      { id: 1, name: "Version 2.3", starts_on: "2026-07-31", ends_on: "2026-09-09", order: 1 },
      { id: 2, name: "Version 2.4", starts_on: "2026-09-09", ends_on: "2099-10-14", order: 2 },
    ],
  });
  const tickets = [
    makeTicket({
      id: 1,
      title: "Export PDF",
      milestone: { id: 1, name: "Version 2.3" },
      client_label: "Livrée",
      is_closed: true,
    }),
    makeTicket({ id: 2, title: "Filtre par date", milestone: { id: 2, name: "Version 2.4" } }),
    makeTicket({ id: 3, title: "Stats mensuelles", milestone: null }),
  ];
  renderApp(
    <WhenLoggedIn>
      <Roadmap project="SCV" tickets={tickets} />
    </WhenLoggedIn>,
  );
  expect(await screen.findByText("1/1 livrées")).toBeTruthy();
  expect(screen.getByText("Filtre par date")).toBeTruthy(); // version en cours sélectionnée
  expect(screen.getByText("Pas encore planifié")).toBeTruthy();
  expect(screen.queryByText("＋ Nouvelle version")).toBeNull(); // client : lecture seule
});
