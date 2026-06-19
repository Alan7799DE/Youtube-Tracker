import { NavLink, Outlet } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../auth/useAuth";

const MENUS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/campaigns", label: "Campañas" },
  { to: "/channels", label: "Canales" },
  { to: "/review", label: "Revisión" },
];

export function AppShell() {
  const { user } = useAuth();
  return (
    <div className="app-shell">
      <nav aria-label="principal" className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">✓</span>
          <span className="brand-text">Verificador<span className="brand-accent">YT</span></span>
        </div>
        <p className="nav-label">Monitoreo</p>
        <ul>
          {MENUS.map((m) => (
            <li key={m.to}>
              <NavLink to={m.to} end={m.end}>{m.label}</NavLink>
            </li>
          ))}
        </ul>
        <div aria-label="cuenta" className="account">
          <span className="account-email">{user?.email}</span>
          <button type="button" className="ghost-btn" onClick={() => supabase.auth.signOut()}>Cerrar sesión</button>
        </div>
      </nav>
      <main><Outlet /></main>
    </div>
  );
}
