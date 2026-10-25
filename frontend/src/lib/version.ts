import { createContext } from "react";

/** Compteur de mutations, fourni par UIProvider ; 0 hors provider (tests). */
export const UIVersionContext = createContext(0);
