import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, hasSession, login as apiLogin, logout as apiLogout } from "../lib/api";
import type { Me } from "../lib/types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
  /** Adopte une session déjà ouverte (après invitation / réinitialisation). */
  adopt: (me: Me) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(hasSession());

  useEffect(() => {
    if (!hasSession()) return;
    api<Me>("/me")
      .then(setMe)
      .catch(apiLogout)
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const user = await apiLogin(email, password);
    setMe(user);
    return user;
  }, []);
  const logout = useCallback(() => {
    apiLogout();
    setMe(null);
  }, []);

  return <AuthContext.Provider value={{ me, loading, login, logout, adopt: setMe }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth hors AuthProvider");
  return ctx;
}

/** Utilisateur connecté garanti (dans les espaces protégés). */
export function useMe(): Me {
  const { me } = useAuth();
  if (!me) throw new Error("non connecté");
  return me;
}
