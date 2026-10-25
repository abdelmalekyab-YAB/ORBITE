import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { useAuth } from "../auth/AuthContext";
import { BallBadge, Track } from "../components/bits";
import NewRequestModal from "../components/NewRequestModal";
import { useUI } from "../components/UIContext";
import { julie, makeTicket, mockApi, renderApp, STEPS } from "./utils";

afterEach(() => vi.unstubAllGlobals());

test("la piste masque « Proposition à valider » hors devis et marque l'étape courante", async () => {
  mockApi({ "GET /me": julie, "GET /workflow": { statuses: [], steps: STEPS } });
  const { container } = renderApp(<Track ticket={makeTicket()} labels />);
  await waitFor(() => expect(container.querySelectorAll(".track.lbl div").length).toBe(6));
  expect(container.querySelector(".cur")?.textContent).toBe("À tester");
  expect(screen.queryByText("Proposition à valider")).toBeNull();
});

test("la balle : à vous / chez Digitalia / en retard", () => {
  mockApi({ "GET /me": julie, "GET /workflow": { statuses: [], steps: STEPS } });
  renderApp(
    <>
      <BallBadge ticket={makeTicket()} />
      <BallBadge ticket={makeTicket({ ball: "digitalia", is_late: true })} />
    </>,
  );
  expect(screen.getByText("À vous")).toBeTruthy();
  expect(screen.getByText("En retard · Digitalia")).toBeTruthy();
});

function OpenModal() {
  const { me } = useAuth();
  const { setNewRequest } = useUI();
  useEffect(() => {
    if (me) setNewRequest(true);
  }, [me, setNewRequest]);
  return me ? <NewRequestModal /> : null;
}

test("nouvelle demande en 3 étapes : type, récit + impact, récapitulatif", async () => {
  const calls = mockApi({
    "GET /me": julie,
    "GET /workflow": { statuses: [], steps: STEPS },
    "POST /tickets": makeTicket({ id: 11, ref: "SCV-11", status: "nouveau" }),
  });
  renderApp(<OpenModal />);
  fireEvent.click(await screen.findByText("Quelque chose ne marche pas"));
  fireEvent.click(screen.getByText("Continuer →"));
  fireEvent.change(screen.getByPlaceholderText(/Erreur à l'export/), { target: { value: "Le bouton ne répond plus" } });
  fireEvent.click(screen.getByText("Bloquant"));
  fireEvent.click(screen.getByText("Continuer →"));
  expect(screen.getByText("On récapitule")).toBeTruthy();
  fireEvent.click(screen.getByText("Envoyer la demande"));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/tickets")).toBe(true));
  const body = calls.find((c) => c.path === "/tickets")!.body as FormData;
  expect(Object.fromEntries(body.entries())).toMatchObject({ project: "SCV", type: "bug", impact: "bloquant" });
});

test("un client n'accède pas à l'espace Digitalia", async () => {
  mockApi({
    "GET /me": julie,
    "GET /workflow": { statuses: [], steps: STEPS },
    "GET /tickets": { results: [] },
    "GET /projects/SCV": { milestones: [] },
    "GET /activity": [],
  });
  localStorage.setItem("orbit.access", "token");
  const { MemoryRouter } = await import("react-router-dom");
  const { render } = await import("@testing-library/react");
  render(
    <MemoryRouter initialEntries={["/dig/kanban"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Mes demandes")).toBeTruthy();
  expect(screen.queryByText("Kanban")).toBeNull();
});
