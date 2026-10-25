import { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { UIProvider } from "./components/UIContext";
import ClientSpace from "./pages/client/ClientSpace";
import DigitaliaSpace from "./pages/dig/DigitaliaSpace";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import { ForgotPasswordPage, SetPasswordPage } from "./pages/PasswordPages";

/** Protège un espace : connecté, et du bon côté (client / Digitalia). Les droits réels sont vérifiés par l'API. */
function Guard({ side, children }: { side: "client" | "digitalia"; children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return null;
  if (!me) return <Navigate to="/login" replace />;
  if (me.is_digitalia !== (side === "digitalia")) return <Navigate to={me.is_digitalia ? "/dig" : "/app"} replace />;
  return <UIProvider>{children}</UIProvider>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/invitation" element={<SetPasswordPage kind="invite" />} />
        <Route path="/reinitialiser" element={<SetPasswordPage kind="reset" />} />
        <Route path="/mot-de-passe-oublie" element={<ForgotPasswordPage />} />
        <Route
          path="/app/*"
          element={
            <Guard side="client">
              <ClientSpace />
            </Guard>
          }
        />
        <Route
          path="/dig/*"
          element={
            <Guard side="digitalia">
              <DigitaliaSpace />
            </Guard>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
