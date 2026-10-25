import { FormEvent, ReactNode, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError, api, setPassword } from "../lib/api";

function Frame({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div className="login" style={{ gridTemplateColumns: "1fr", maxWidth: 520 }}>
      <div className="box">
        <img src={`${import.meta.env.BASE_URL}logo-digitalia.png`} alt="Digitalia" style={{ height: 34, marginBottom: 14 }} />
        <h2>{title}</h2>
        <p className="hint">{hint}</p>
        {children}
      </div>
    </div>
  );
}

/** Invitation (« Créer mon mot de passe ») et réinitialisation : même formulaire, lien signé uid + token. */
export function SetPasswordPage({ kind }: { kind: "invite" | "reset" }) {
  const [params] = useSearchParams();
  const { adopt } = useAuth();
  const navigate = useNavigate();
  const [password, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const uid = params.get("uid") ?? "";
  const token = params.get("token") ?? "";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 8) return setError("Au moins 8 caractères.");
    if (password !== confirm) return setError("Les deux mots de passe ne correspondent pas.");
    setBusy(true);
    try {
      const me = await setPassword(kind, uid, token, password);
      adopt(me);
      navigate(me.is_digitalia ? "/dig" : "/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible pour le moment.");
    } finally {
      setBusy(false);
    }
  }

  if (!uid || !token) {
    return (
      <Frame title="Lien incomplet" hint="Ouvrez le lien reçu par e-mail, ou demandez-en un nouveau.">
        <Link to="/mot-de-passe-oublie" className="btn white" style={{ marginTop: 14 }}>
          Recevoir un nouveau lien
        </Link>
      </Frame>
    );
  }
  return (
    <Frame
      title={kind === "invite" ? "Bienvenue sur Orbit" : "Nouveau mot de passe"}
      hint={
        kind === "invite" ? "Choisissez votre mot de passe pour accéder à votre espace." : "Choisissez un nouveau mot de passe."
      }
    >
      <form onSubmit={submit} style={{ display: "grid", gap: 14, marginTop: 16 }}>
        <label className="field">
          Mot de passe
          <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPwd(e.target.value)} required />
        </label>
        <label className="field">
          Confirmer le mot de passe
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </label>
        <p className="hint">8 caractères minimum, pas uniquement des chiffres ni un mot de passe trop courant.</p>
        {error && (
          <p role="alert" style={{ color: "var(--rose)", fontSize: 13 }}>
            {error}
          </p>
        )}
        <button className="btn white" style={{ justifyContent: "center", padding: 13 }} disabled={busy}>
          {kind === "invite" ? "Créer mon mot de passe →" : "Enregistrer →"}
        </button>
      </form>
    </Frame>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api<{ detail: string }>(
        "/auth/password/forgot",
        { method: "POST", body: JSON.stringify({ email }) },
        false,
      );
      setSent(r.detail);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Frame title="Mot de passe oublié" hint="Indiquez votre e-mail : vous recevrez un lien pour choisir un nouveau mot de passe.">
      {sent ? (
        <p className="banner b-you" style={{ marginTop: 16 }} role="status">
          {sent}
        </p>
      ) : (
        <form onSubmit={submit} style={{ display: "grid", gap: 14, marginTop: 16 }}>
          <label className="field">
            E-mail
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <button className="btn white" style={{ justifyContent: "center", padding: 13 }} disabled={busy}>
            Recevoir le lien →
          </button>
        </form>
      )}
      <p className="hint" style={{ marginTop: 14 }}>
        <Link to="/login">← Retour à la connexion</Link>
      </p>
    </Frame>
  );
}
