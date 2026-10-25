import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom n'implémente pas les URL d'objets (aperçus de pièces jointes).
URL.createObjectURL ??= () => "blob:test";
URL.revokeObjectURL ??= () => undefined;

afterEach(() => {
  cleanup();
  localStorage.clear();
});
