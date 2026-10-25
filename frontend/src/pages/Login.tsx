import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/api";

export default function Login() {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to={me.is_digitalia ? "/dig" : "/app"} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const user = await login(email, password);
      navigate(user.is_digitalia ? "/dig" : "/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Connexion impossible pour le moment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <div>
        <img src="/logo-digitalia.png" alt="Digitalia" style={{ height: 40 }} />
        <div className="tagl">✦ DÉVELOPPÉ PAR DIGITALIA POUR SES CLIENTS</div>
        <h1>
          Votre projet,
          <br />
          <span>en temps réel.</span>
        </h1>
        <p>Suivez l'avancement, déposez vos demandes, testez ce qui est livré. Sans relancer personne.</p>
      </div>
      <form className="box" onSubmit={submit}>
        <h2>Se connecter</h2>
        <p className="hint">Avec l'adresse e-mail communiquée à Digitalia.</p>
        <div style={{ display: "grid", gap: 14 }}>
          <label className="field">
            E-mail
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field">
            Mot de passe
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && (
            <p style={{ color: "var(--rose)", fontSize: 13 }} role="alert">
              {error}
            </p>
          )}
          <button className="btn white" style={{ justifyContent: "center", padding: 13 }} disabled={busy}>
            Accéder à mon espace →
          </button>
          <div className="hint" style={{ display: "flex", justifyContent: "space-between" }}>
            <Link to="/mot-de-passe-oublie">Mot de passe oublié ?</Link>
            <span>Pas encore d'accès ? Contactez Digitalia.</span>
          </div>
        </div>
      </form>
    </div>
  );
}
