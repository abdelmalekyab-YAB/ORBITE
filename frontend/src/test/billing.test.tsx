import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { FinanceModule } from "../finance/FinanceModule";
import { mockApi } from "./utils";

afterEach(() => vi.unstubAllGlobals());

test("le module Facturation appelle l'API billing d'Orbit avec le jeton", async () => {
  localStorage.setItem("orbit.access", "token");
  const calls = mockApi({ "GET /billing/profiles/": [], "GET /billing/orbit-projects/": [] });
  render(<FinanceModule />);
  expect(screen.getByRole("button", { name: "Tableau de bord" })).toBeTruthy();
  await waitFor(() => expect(calls.some((c) => c.path === "/billing/dashboard/")).toBe(true));
  const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
  expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token");
});
