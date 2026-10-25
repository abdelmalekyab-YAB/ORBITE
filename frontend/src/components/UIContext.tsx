import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Workflow } from "../lib/types";
import { UIVersionContext } from "../lib/version";

export type DrawerIntent = "testko" | "reopen" | null;

interface UIState {
  /** Incrémenté après chaque mutation : les listes se rechargent. */
  version: number;
  bump: () => void;
  ticketId: number | null;
  /** Ouvre la fiche ; `intent` = ouvrir directement le bloc de refus (« Pas OK »). */
  openTicket: (id: number | null, intent?: DrawerIntent) => void;
  drawerIntent: DrawerIntent;
  newRequest: boolean;
  setNewRequest: (open: boolean) => void;
  toast: (msg: string) => void;
  workflow: Workflow | null;
}

const UIContext = createContext<UIState | null>(null);

export function UIProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [drawerIntent, setDrawerIntent] = useState<DrawerIntent>(null);
  const openTicket = useCallback((id: number | null, intent: DrawerIntent = null) => {
    setTicketId(id);
    setDrawerIntent(intent);
  }, []);
  const [newRequest, setNewRequest] = useState(false);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [message, setMessage] = useState("");
  const timer = useRef<number>();

  useEffect(() => {
    api<Workflow>("/workflow")
      .then(setWorkflow)
      .catch(() => undefined);
  }, [version]); // rechargé après une modification (ex. réglages du workflow)

  const toast = useCallback((msg: string) => {
    setMessage(msg);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMessage(""), 2600);
  }, []);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <UIContext.Provider value={{ version, bump, ticketId, openTicket, drawerIntent, newRequest, setNewRequest, toast, workflow }}>
      <UIVersionContext.Provider value={version}>{children}</UIVersionContext.Provider>
      <div className={`toast ${message ? "show" : ""}`} role="status">
        {message}
      </div>
    </UIContext.Provider>
  );
}

export function useUI() {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI hors UIProvider");
  return ctx;
}
