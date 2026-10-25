import type { Me } from "./types";

// The API lives next to the app (same origin, also when it is served under a sub-path).
const BASE = `${import.meta.env.BASE_URL}api/v1`;
const ACCESS = "orbit.access";
const REFRESH = "orbit.refresh";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
  }
}

async function refreshAccess(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH);
  if (!refresh) return false;
  const res = await fetch(BASE + "/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return false;
  localStorage.setItem(ACCESS, (await res.json()).access);
  return true;
}

/** Appel JSON, ou multipart si `body` est un FormData. Rafraîchit le jeton une fois sur 401. */
export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const token = localStorage.getItem(ACCESS);
  const isForm = init.body instanceof FormData;
  const res = await fetch(BASE + path, {
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (res.status === 401 && retry && token && (await refreshAccess())) return api<T>(path, init, false);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail ?? `Erreur ${res.status}`, data.code);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

/** FormData avec champs simples + pièces jointes sous la clé `attachments`. */
export function formData(fields: Record<string, string | number | boolean | null | undefined>, files: File[] = []) {
  const fd = new FormData();
  Object.entries(fields).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && fd.append(k, String(v)));
  files.forEach((f) => fd.append("attachments", f, f.name));
  return fd;
}

export interface Session {
  access: string;
  refresh: string;
  me: Me;
}

export function storeSession(t: Session): Me {
  localStorage.setItem(ACCESS, t.access);
  localStorage.setItem(REFRESH, t.refresh);
  return t.me;
}

export async function login(email: string, password: string): Promise<Me> {
  return storeSession(await api<Session>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false));
}

/** Invitation ou réinitialisation : définit le mot de passe et ouvre la session. */
export async function setPassword(kind: "invite" | "reset", uid: string, token: string, password: string): Promise<Me> {
  const path = kind === "invite" ? "/auth/invite/accept" : "/auth/password/reset";
  return storeSession(await api<Session>(path, { method: "POST", body: JSON.stringify({ uid, token, password }) }, false));
}

export function logout() {
  localStorage.removeItem(ACCESS);
  localStorage.removeItem(REFRESH);
}

export const hasSession = () => Boolean(localStorage.getItem(ACCESS));

/** Téléchargement authentifié (exports CSV) : le jeton ne passe jamais dans l'URL. */
export async function download(path: string, filename: string) {
  const token = localStorage.getItem(ACCESS);
  const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, `Export impossible (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
