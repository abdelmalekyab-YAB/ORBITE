import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import TicketDrawer from "../components/TicketDrawer";
import { useUI } from "../components/UIContext";
import { julie, makeTicket, mockApi, renderApp, STEPS } from "./utils";

afterEach(() => vi.unstubAllGlobals());

function OpenDrawer({ id }: { id: number }) {
  const { me } = useAuth();
  const { openTicket } = useUI();
  useEffect(() => {
    if (me) openTicket(id);
  }, [me, id, openTicket]);
  return me ? <TicketDrawer /> : null;
}

function setup(ticket = makeTicket()) {
  return mockApi({
    "GET /me": julie,
    "GET /workflow": { statuses: [], steps: STEPS },
    [`GET /tickets/${ticket.id}`]: ticket,
    [`GET /tickets/${ticket.id}/events`]: [],
    [`POST /tickets/${ticket.id}/transition`]: makeTicket({
      status: "cours",
      ball: "digitalia",
      client_label: "En développement",
    }),
  });
}

test("« Pas OK » est bloqué sans motif (règle 10)", async () => {
  const calls = setup();
  renderApp(<OpenDrawer id={10} />);
  fireEvent.click(await screen.findByText(/Pas OK/));
  fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "non" } });
  fireEvent.click(screen.getByText("Envoyer mon refus"));
  expect(await screen.findByText(/10 caractères minimum/)).toBeTruthy();
  expect(calls.some((c) => c.path.endsWith("/transition"))).toBe(false);
});

test("« Pas OK » avec un motif envoie la transition test → cours avec le commentaire", async () => {
  const calls = setup();
  renderApp(<OpenDrawer id={10} />);
  fireEvent.click(await screen.findByText(/Pas OK/));
  fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "Le filtre ignore la date de fin." } });
  fireEvent.click(screen.getByText("Envoyer mon refus"));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/transition"))).toBe(true));
  const body = calls.find((c) => c.path.endsWith("/transition"))!.body as FormData;
  expect(body.get("to")).toBe("cours");
  expect(body.get("comment")).toBe("Le filtre ignore la date de fin.");
});

test("un message vocal suffit comme motif", async () => {
  const calls = setup();
  renderApp(<OpenDrawer id={10} />);
  fireEvent.click(await screen.findByText(/Pas OK/));
  const audio = document.querySelector<HTMLInputElement>('.refus input[accept="audio/*"]')!;
  fireEvent.change(audio, { target: { files: [new File(["x"], "vocal.webm", { type: "audio/webm" })] } });
  fireEvent.click(screen.getByText("Envoyer mon refus"));
  await waitFor(() => expect(calls.some((c) => c.path.endsWith("/transition"))).toBe(true));
  const body = calls.find((c) => c.path.endsWith("/transition"))!.body as FormData;
  expect((body.get("attachments") as File).type).toBe("audio/webm");
});

test("le client ne voit pas les champs de pilotage Digitalia", async () => {
  setup();
  renderApp(<OpenDrawer id={10} />);
  await screen.findByText("Filtre par date");
  expect(screen.queryByLabelText("Responsable")).toBeNull();
  expect(screen.queryByLabelText("Visibilité")).toBeNull();
});
