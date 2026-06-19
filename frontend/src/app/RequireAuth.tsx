import type { ReactNode } from "react";
import { useAuth } from "../auth/useAuth";
import { LoginPage } from "../auth/LoginPage";

// Guard de sesión: mientras carga muestra un placeholder, sin sesión muestra el
// login, y con sesión renderiza la app. Toda la app vive detrás de este guard.
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p>Loading…</p>;
  if (!user) return <LoginPage />;
  return <>{children}</>;
}
