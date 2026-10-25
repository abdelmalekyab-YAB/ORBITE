import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import Landing from "../pages/Landing";

test("l'accueil public propose l'accès à l'espace", () => {
  render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  );
  expect(screen.getByText(/Accéder à mon espace/)).toBeTruthy();
});
