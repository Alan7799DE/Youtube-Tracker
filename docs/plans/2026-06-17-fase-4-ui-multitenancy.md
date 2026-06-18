# Fase 4 — Interfaz web + multi-tenancy · Plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDO: usá `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkboxes (`- [ ]`) para tracking. Para el pulido visual de cada vista, usá el skill `frontend-design`.

**Goal:** una app web React multi-usuario donde cada persona se registra (con organización personal automática), importa canales, crea campañas con su brief, ve el estado de cada canal-campaña y resuelve la cola de revisión — hablando **únicamente con Supabase** (lee y escribe toda la config por RLS). **No hay API backend.**

**Architecture:** frontend React + Vite + TypeScript que lee y escribe contra Supabase con la *anon key* gobernada por RLS. **Toda la config la escribe la UI por RLS** (campañas, requisitos, asignaciones, reviews, y las filas de canal). El **archivo de canales se parsea en el cliente** y la **reconciliación** del import se computa en el cliente; el **brief es un formulario manual** (sin subida de archivo ni LLM). La resolución de canales (`unresolved` → `channel_id`) y la suscripción WebSub las hace el **cron tick del backend** (Fases 2–3), de forma asíncrona. El frontend nunca llama al backend. La organización personal se crea sola por el trigger del `schema.sql`.

**Tech Stack:** React 18, Vite, TypeScript, `@supabase/supabase-js` v2, `react-router-dom` v6, `xlsx` (SheetJS, parseo de CSV/`.xlsx` en el cliente), Vitest + `@testing-library/react` + jsdom. Pulido visual: skill `frontend-design`. **No hay backend nuevo en esta fase.**

**Alcance (diseño, sección 15 · Fase 4 + sección 8):**
- **Entra:** auth + organización personal, app shell con los 4 menús, dashboard, detalle de video, gestión de campañas (brief por **formulario manual**, asignación de canales, plazo), grilla de importación de canales (parseo + reconciliación en el cliente), cola de revisión. Multi-tenancy efectiva (RLS por org ya en el schema).
- **No entra:** notificaciones (Fase 5), robustez/escala (Fase 6). La resolución/WebSub la hace el cron tick (Fase 3), no la UI.

**Prerrequisito:** Fases 1–3 implementadas; un proyecto Supabase con el `schema.sql` corrido.

**Sobre el formato:** las tareas de **lógica** (mapeo de estados, auth, data layer, parseo, reconciliación) van en TDD estricto con código real. Las tareas de **vistas visuales** dan una especificación concreta (datos, estados, acciones) + un test de lógica/smoke, y el armado visual fino se hace con el skill `frontend-design`. No usar placeholders en el código de lógica.

---

## Estructura de archivos

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  vitest.config.ts
  .env.example                 # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
  src/
    lib/
      supabase.ts              # cliente supabase (anon)
      types.ts                 # tipos de las tablas del schema
      status.ts                # estado -> badge (label/tone)  [TDD]
      parseChannels.ts         # archivo CSV/xlsx -> list[str] de URLs (cliente)  [TDD]
      reconcile.ts             # (urls nuevas, existentes) -> plan add/keep/deactivate/reactivate  [TDD]
    auth/
      AuthProvider.tsx         # contexto de sesión (Supabase Auth)
      useAuth.ts
      LoginPage.tsx
    app/
      AppShell.tsx             # layout + barra lateral (4 menús + cuenta)
      router.tsx
    data/
      channels.ts              # queries RLS de canales (read + write/reconcile)
      campaigns.ts             # queries RLS de campañas/requisitos/asignaciones
      videos.ts                # queries RLS de videos/verificaciones
      reviews.ts               # insert de review
    pages/
      DashboardPage.tsx
      ChannelsPage.tsx
      CampaignsPage.tsx
      CampaignEditor.tsx
      VideoDetailPage.tsx
      ReviewQueuePage.tsx
  src/**/*.test.ts(x)          # Vitest
```

> **Sin backend nuevo en esta fase.** El frontend habla solo con Supabase (RLS). La resolución de canales y el WebSub los maneja el cron tick de la Fase 3.

---

## Tarea 0: Scaffolding del frontend

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/vitest.config.ts`, `frontend/.env.example`, `frontend/index.html`, `frontend/src/main.tsx`

- [ ] **Step 1: Crear `frontend/package.json`**

```json
{
  "name": "verificador-ui",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@supabase/supabase-js": "^2.45.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "xlsx": "^0.18.5"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.1.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Crear `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({ plugins: [react()] });
```

- [ ] **Step 3: Crear `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: [] },
});
```

- [ ] **Step 4: Crear `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Crear `frontend/.env.example`**

```bash
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

- [ ] **Step 6: Crear `frontend/index.html` y `frontend/src/main.tsx`**

`frontend/index.html`:

```html
<!doctype html>
<html lang="es">
  <head><meta charset="UTF-8" /><title>Verificador YT</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>
```

`frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
```

- [ ] **Step 7: Instalar y verificar**

Run: `cd frontend && npm install && npm run test`
Expected: instala; `vitest run` corre y dice "no test files" (todavía).

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/vitest.config.ts frontend/.env.example frontend/index.html frontend/src/main.tsx
git commit -m "chore: scaffolding del frontend React (Fase 4)"
```

---

## Tarea 1: Cliente Supabase y tipos de tablas

**Files:**
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: Crear `frontend/src/lib/supabase.ts`**

```ts
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL as string,
  import.meta.env.VITE_SUPABASE_ANON_KEY as string
);
```

- [ ] **Step 2: Crear `frontend/src/lib/types.ts`**

```ts
export type ResolutionStatus = "resolved" | "unresolved" | "ambiguous";
export type ChannelCampaignStatus = "pending" | "verified" | "incomplete" | "failed";
export type VideoStatus = "detected" | "awaiting_transcript" | "verifying" | "resolved" | "needs_human" | "error";
export type OverallStatus = "pass" | "fail" | "review";

export interface Channel {
  id: string;
  source_url: string;
  handle: string | null;
  name: string | null;
  youtube_channel_id: string | null;
  resolution_status: ResolutionStatus;
  is_active: boolean;
}

export interface Campaign {
  id: string;
  brand: string;
  name: string;
  status: "active" | "closed";
  starts_at: string | null;
  ends_at: string;
}

export interface Requirement {
  id: string;
  campaign_id: string;
  code: string;
  type: "link_in_desc" | "code_in_desc" | "mention_name" | "describe_game" | "show_gameplay";
  spec: Record<string, unknown>;
  method: "deterministic" | "llm" | "human";
  required: boolean;
}

export interface CampaignChannel {
  id: string;
  campaign_id: string;
  channel_id: string;
  status: ChannelCampaignStatus;
}

export interface VideoSubmission {
  id: string;
  channel_id: string;
  youtube_video_id: string;
  title: string | null;
  url: string | null;
  status: VideoStatus;
}

export interface Verification {
  id: string;
  video_id: string;
  campaign_id: string;
  overall_status: OverallStatus;
}

export interface RequirementResult {
  id: string;
  verification_id: string;
  requirement_id: string;
  met: boolean;
  confidence: number | null;
  evidence: string | null;
  evidence_timestamp_s: number | null;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/supabase.ts frontend/src/lib/types.ts
git commit -m "feat: cliente Supabase y tipos de tablas"
```

---

## Tarea 2: Mapeo de estados a badges (TDD)

**Files:**
- Create: `frontend/src/lib/status.ts`
- Test: `frontend/src/lib/status.test.ts`

- [ ] **Step 1: Escribir el test que falla**

```ts
import { describe, it, expect } from "vitest";
import { channelStatusBadge, dashboardRowBadge } from "./status";

describe("channelStatusBadge", () => {
  it("verified -> Cumple/success", () => {
    expect(channelStatusBadge("verified")).toEqual({ label: "Cumple", tone: "success" });
  });
  it("incomplete -> Incompleto/warning", () => {
    expect(channelStatusBadge("incomplete")).toEqual({ label: "Incompleto", tone: "warning" });
  });
  it("failed -> No cumplió/danger", () => {
    expect(channelStatusBadge("failed")).toEqual({ label: "No cumplió", tone: "danger" });
  });
  it("pending -> Pendiente/neutral", () => {
    expect(channelStatusBadge("pending")).toEqual({ label: "Pendiente", tone: "neutral" });
  });
});

describe("dashboardRowBadge", () => {
  it("muestra 'En revisión' cuando hay un video en review y sigue pending", () => {
    expect(dashboardRowBadge("pending", true)).toEqual({ label: "En revisión", tone: "info" });
  });
  it("usa el estado del canal-campaña si no hay review pendiente", () => {
    expect(dashboardRowBadge("verified", false)).toEqual({ label: "Cumple", tone: "success" });
  });
  it("un estado terminal gana sobre el review", () => {
    expect(dashboardRowBadge("verified", true)).toEqual({ label: "Cumple", tone: "success" });
  });
});
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/lib/status.test.ts`
Expected: FAIL (no existe `status.ts`).

- [ ] **Step 3: Implementar `frontend/src/lib/status.ts`**

```ts
import type { ChannelCampaignStatus } from "./types";

export type Tone = "success" | "warning" | "danger" | "neutral" | "info";
export interface Badge { label: string; tone: Tone; }

const MAP: Record<ChannelCampaignStatus, Badge> = {
  verified: { label: "Cumple", tone: "success" },
  incomplete: { label: "Incompleto", tone: "warning" },
  failed: { label: "No cumplió", tone: "danger" },
  pending: { label: "Pendiente", tone: "neutral" },
};

export function channelStatusBadge(status: ChannelCampaignStatus): Badge {
  return MAP[status];
}

export const REVIEW_BADGE: Badge = { label: "En revisión", tone: "info" };

// El dashboard muestra 5 estados: si el canal-campaña sigue 'pending' pero tiene
// un video esperando revisión humana, se muestra "En revisión" (derivado del video).
export function dashboardRowBadge(status: ChannelCampaignStatus, hasVideoInReview: boolean): Badge {
  if (status === "pending" && hasVideoInReview) return REVIEW_BADGE;
  return channelStatusBadge(status);
}
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/lib/status.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/status.ts frontend/src/lib/status.test.ts
git commit -m "feat: mapeo de estados a badges"
```

---

## Tarea 3: Canales — parseo y reconciliación (en el cliente, TDD)

El frontend parsea el archivo de canales y computa la reconciliación; después escribe por RLS (sin backend). Dos módulos puros, testeables con Vitest.

**Files:**
- Create: `frontend/src/lib/parseChannels.ts`, `frontend/src/lib/reconcile.ts`
- Test: `frontend/src/lib/parseChannels.test.ts`, `frontend/src/lib/reconcile.test.ts`

- [ ] **Step 1: Escribir el test de parseo que falla**

```ts
import { describe, it, expect } from "vitest";
import { parseChannelsFile } from "./parseChannels";

describe("parseChannelsFile", () => {
  it("toma la primera columna y saltea el header y las filas vacías", () => {
    const csv = "url\nhttps://youtube.com/@a\n\nhttps://youtube.com/@b\n";
    const buf = new TextEncoder().encode(csv).buffer;
    expect(parseChannelsFile(buf)).toEqual(["https://youtube.com/@a", "https://youtube.com/@b"]);
  });
});
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/lib/parseChannels.test.ts`
Expected: FAIL (no existe `parseChannels.ts`).

- [ ] **Step 3: Implementar `frontend/src/lib/parseChannels.ts`**

```ts
import * as XLSX from "xlsx";

const HEADER = new Set(["url", "urls", "canal", "canales", "channel", "channels", "link", "links"]);

// Lee CSV o .xlsx (SheetJS autodetecta) y devuelve la primera columna, sin header ni vacíos.
export function parseChannelsFile(data: ArrayBuffer): string[] {
  const wb = XLSX.read(data, { type: "array" });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, blankrows: false });
  const out: string[] = [];
  rows.forEach((row, i) => {
    const v = String(row?.[0] ?? "").trim();
    if (!v) return;
    if (i === 0 && HEADER.has(v.toLowerCase())) return;
    out.push(v);
  });
  return out;
}
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/lib/parseChannels.test.ts`
Expected: PASS (1 test).

- [ ] **Step 5: Escribir el test de reconciliación que falla**

```ts
import { describe, it, expect } from "vitest";
import { reconcile } from "./reconcile";

describe("reconcile", () => {
  it("agrega, mantiene, desactiva y reactiva (case/slash-insensitive)", () => {
    const newUrls = ["https://YouTube.com/@A/", "https://youtube.com/@c", "https://youtube.com/@d"];
    const existing = [
      { id: "1", source_url: "https://youtube.com/@a", is_active: true },
      { id: "2", source_url: "https://youtube.com/@b", is_active: true },
      { id: "4", source_url: "https://youtube.com/@d", is_active: false },
    ];
    const plan = reconcile(newUrls, existing);
    expect(plan.toAdd).toEqual(["https://youtube.com/@c"]);
    expect(plan.toKeep.map((c) => c.id)).toEqual(["1"]);
    expect(plan.toDeactivate.map((c) => c.id)).toEqual(["2"]);
    expect(plan.toReactivate.map((c) => c.id)).toEqual(["4"]);
  });
});
```

- [ ] **Step 6: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/lib/reconcile.test.ts`
Expected: FAIL (no existe `reconcile.ts`).

- [ ] **Step 7: Implementar `frontend/src/lib/reconcile.ts`**

```ts
export interface ExistingChannel { id: string; source_url: string; is_active: boolean; }
export interface ReconcilePlan {
  toAdd: string[];
  toKeep: ExistingChannel[];
  toDeactivate: ExistingChannel[];
  toReactivate: ExistingChannel[];
}

const norm = (u: string) => u.trim().toLowerCase().replace(/\/+$/, "");

export function reconcile(newUrls: string[], existing: ExistingChannel[]): ReconcilePlan {
  const newSet = new Set(newUrls.map(norm));
  const existingNorms = new Set(existing.map((c) => norm(c.source_url)));

  const toAdd: string[] = [];
  const seen = new Set<string>();
  for (const u of newUrls) {
    const n = norm(u);
    if (!existingNorms.has(n) && !seen.has(n)) { seen.add(n); toAdd.push(u); }
  }

  const toKeep: ExistingChannel[] = [];
  const toDeactivate: ExistingChannel[] = [];
  const toReactivate: ExistingChannel[] = [];
  for (const c of existing) {
    const inNew = newSet.has(norm(c.source_url));
    if (inNew && c.is_active) toKeep.push(c);
    else if (inNew && !c.is_active) toReactivate.push(c);
    else if (!inNew && c.is_active) toDeactivate.push(c);
  }
  return { toAdd, toKeep, toDeactivate, toReactivate };
}
```

- [ ] **Step 8: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/lib/reconcile.test.ts`
Expected: PASS (1 test).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/parseChannels.ts frontend/src/lib/parseChannels.test.ts frontend/src/lib/reconcile.ts frontend/src/lib/reconcile.test.ts
git commit -m "feat: parseo y reconciliación de canales en el cliente"
```

> La página de canales (Tarea 7) usa estos dos módulos: parsea el archivo, reconcilia contra la grilla y aplica el plan por RLS (insertar nuevos como `unresolved`, marcar `is_active`). El backend (cron tick, Fase 3) resuelve después.

---

## Tarea 4: Autenticación y login

**Files:**
- Create: `frontend/src/auth/AuthProvider.tsx`, `frontend/src/auth/useAuth.ts`, `frontend/src/auth/LoginPage.tsx`
- Test: `frontend/src/auth/AuthProvider.test.tsx`

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

vi.mock("../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { user: { id: "u1", email: "a@b.com" } } } }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}));

function Probe() {
  const { user } = useAuth();
  return <div>{user ? user.email : "anon"}</div>;
}

describe("AuthProvider", () => {
  it("expone el usuario de la sesión", async () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByText("a@b.com")).toBeTruthy());
  });
});
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/auth/AuthProvider.test.tsx`
Expected: FAIL (no existen los módulos).

- [ ] **Step 3: Implementar auth**

`frontend/src/auth/useAuth.ts`:

```ts
import { createContext, useContext } from "react";
import type { User } from "@supabase/supabase-js";

export interface AuthState { user: User | null; loading: boolean; }
export const AuthContext = createContext<AuthState>({ user: null, loading: true });
export const useAuth = () => useContext(AuthContext);
```

`frontend/src/auth/AuthProvider.tsx`:

```tsx
import { useEffect, useState, type ReactNode } from "react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import { AuthContext } from "./useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_e, session) => {
      setUser(session?.user ?? null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>;
}
```

`frontend/src/auth/LoginPage.tsx`:

```tsx
import { useState } from "react";
import { supabase } from "../lib/supabase";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const fn = mode === "login" ? supabase.auth.signInWithPassword : supabase.auth.signUp;
    const { error } = await fn({ email, password });
    if (error) setError(error.message);
  }

  return (
    <form onSubmit={submit}>
      <h1>{mode === "login" ? "Ingresar" : "Crear cuenta"}</h1>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Contraseña" />
      <button type="submit">{mode === "login" ? "Ingresar" : "Registrarme"}</button>
      <button type="button" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
        {mode === "login" ? "Crear cuenta" : "Ya tengo cuenta"}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
```

> Al registrarse, el trigger `handle_new_user` del `schema.sql` crea la organización personal automáticamente. Visual fino del login: skill `frontend-design`.

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/auth/AuthProvider.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/
git commit -m "feat: autenticación con Supabase + login/registro"
```

---

## Tarea 5: App shell + routing (barra lateral de 4 menús)

**Files:**
- Create: `frontend/src/app/AppShell.tsx`, `frontend/src/app/router.tsx`
- Test: `frontend/src/app/AppShell.test.tsx`

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../lib/supabase", () => ({ supabase: { auth: { signOut: vi.fn() } } }));

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("muestra los 4 menús principales y el botón de cerrar sesión", () => {
    render(<MemoryRouter><AppShell /></MemoryRouter>);
    for (const label of ["Dashboard", "Campañas", "Canales", "Revisión"]) {
      expect(screen.getByRole("link", { name: label })).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeTruthy();
  });
});
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/app/AppShell.test.tsx`
Expected: FAIL (no existe `AppShell`).

- [ ] **Step 3: Implementar `frontend/src/app/AppShell.tsx`**

```tsx
import { Link, Outlet } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../auth/useAuth";

const MENUS = [
  { to: "/", label: "Dashboard" },
  { to: "/campaigns", label: "Campañas" },
  { to: "/channels", label: "Canales" },
  { to: "/review", label: "Revisión" },
];

export function AppShell() {
  const { user } = useAuth();
  return (
    <div style={{ display: "flex" }}>
      <nav aria-label="principal">
        <ul>
          {MENUS.map((m) => (
            <li key={m.to}><Link to={m.to}>{m.label}</Link></li>
          ))}
        </ul>
        <div aria-label="cuenta">
          <span>{user?.email}</span>
          <button type="button" onClick={() => supabase.auth.signOut()}>Cerrar sesión</button>
        </div>
      </nav>
      <main><Outlet /></main>
    </div>
  );
}
```

- [ ] **Step 4: Implementar `frontend/src/app/router.tsx`**

```tsx
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "./AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { ChannelsPage } from "../pages/ChannelsPage";
import { CampaignsPage } from "../pages/CampaignsPage";
import { CampaignEditor } from "../pages/CampaignEditor";
import { VideoDetailPage } from "../pages/VideoDetailPage";
import { ReviewQueuePage } from "../pages/ReviewQueuePage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "channels", element: <ChannelsPage /> },
      { path: "campaigns", element: <CampaignsPage /> },
      { path: "campaigns/:id", element: <CampaignEditor /> },
      { path: "videos/:id", element: <VideoDetailPage /> },
      { path: "review", element: <ReviewQueuePage /> },
    ],
  },
]);
```

> Crear stubs mínimos de las 6 páginas (`export function X() { return <div>X</div>; }`) para que el router compile; cada una se completa en su tarea. La protección de rutas por sesión (redirigir a login si no hay user) se agrega envolviendo con `AuthProvider` + un guard; el armado visual de la barra lateral (íconos, badge de Revisión, menú de cuenta) se hace con `frontend-design`.

- [ ] **Step 5: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/app/AppShell.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/ frontend/src/pages/
git commit -m "feat: app shell + routing con los 4 menús"
```

---

## Tarea 6: Data layer de canales (TDD con cliente mockeado)

**Files:**
- Create: `frontend/src/data/channels.ts`
- Test: `frontend/src/data/channels.test.ts`

- [ ] **Step 1: Escribir el test que falla**

```ts
import { describe, it, expect, vi } from "vitest";
import { listChannels } from "./channels";

describe("listChannels", () => {
  it("trae los canales activos de la org via RLS", async () => {
    const order = vi.fn().mockResolvedValue({ data: [{ id: "c1", source_url: "https://youtube.com/@a" }], error: null });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ select });
    const client = { from } as any;

    const rows = await listChannels(client);
    expect(from).toHaveBeenCalledWith("channels");
    expect(eq).toHaveBeenCalledWith("is_active", true);
    expect(rows[0].id).toBe("c1");
  });
});
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/data/channels.test.ts`
Expected: FAIL (no existe `channels.ts`).

- [ ] **Step 3: Implementar `frontend/src/data/channels.ts`**

```ts
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Channel } from "../lib/types";

export async function listChannels(client: SupabaseClient): Promise<Channel[]> {
  const { data, error } = await client
    .from("channels")
    .select("*")
    .eq("is_active", true)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Channel[];
}
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/data/channels.test.ts`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/data/channels.ts frontend/src/data/channels.test.ts
git commit -m "feat: data layer de canales (RLS)"
```

> Replicar el patrón (queries tipadas + test con cliente mockeado) para `campaigns.ts`, `videos.ts` y `reviews.ts` a medida que las páginas las necesiten. Cada función es delgada sobre el cliente Supabase y se testea verificando la cadena de llamadas y el mapeo de filas.

---

## Tareas 7–11: Vistas (especificación + lógica TDD, armado visual con `frontend-design`)

Cada vista se construye en dos pasos: **(a)** un test de la lógica/datos que falla y su implementación mínima (TDD), y **(b)** el armado visual con el skill `frontend-design` según la especificación. Las vistas **leen** de Supabase con RLS y **escriben** la config (campañas/requisitos/asignaciones/reviews) directo por RLS; el brief y las mutaciones de canales pasan por la API (Tarea 3).

### Tarea 7: Página de canales (grilla + importación)

**Files:** `frontend/src/pages/ChannelsPage.tsx`, test asociado.

**Especificación:**
- Grilla editable de canales (columnas: URL, handle/nombre, estado de resolución, activo). Filas agregables/eliminables a mano.
- Botón "Importar archivo" (CSV/`.xlsx`): el cliente parsea con `parseChannelsFile` (Tarea 3), computa el plan con `reconcile` (Tarea 3) contra la grilla actual y **aplica por RLS** (insertar nuevos como `unresolved`, `is_active=true/false` según el plan). No hay backend de por medio; el cron tick (Fase 3) resuelve los `unresolved` después.
- Sección destacada de canales **no resueltos** (`resolution_status='unresolved'`) para corregir a mano.
- **Historial de imports:** lista de las últimas corridas de `import_runs` (fecha, agregados/quitados/no resueltos) leída por RLS.
- Reemplazo total: subir un archivo reemplaza el conjunto activo (reconciliación con soft-deactivate, ya testeada en la Tarea 3).

- [ ] **Step 1 (TDD lógica):** test de `ChannelsPage` que, con `listChannels` mockeado, renderiza una fila por canal y resalta los `unresolved`. Implementar el componente para que pase.
- [ ] **Step 2 (visual):** usar `frontend-design` para la grilla, el botón de import y la sección de no resueltos.
- [ ] **Step 3: Commit** `feat: página de canales (grilla + importación)`.

### Tarea 8: Editor de campañas (brief + asignación + plazo)

**Files:** `frontend/src/pages/CampaignsPage.tsx`, `frontend/src/pages/CampaignEditor.tsx`, tests asociados.

**Especificación:**
- `CampaignsPage`: lista de campañas con su estado; botón "Nueva campaña"; "Cerrar" (no borrar) una campaña → `status='closed'`.
- `CampaignEditor`: form con marca, nombre y **plazo (`ends_at` obligatorio**, validar antes de guardar).
- Brief: **formulario manual estructurado** (sin subir archivo ni LLM): campos para nombre del juego, link esperado, código, y checkboxes de **qué requisitos verificar** (R1–R5). Al guardar, se insertan `campaigns` + `requirements` por RLS (el `spec` de cada requisito sale de los campos del form).
- Asignar canales: multiselección de canales de la org → filas en `campaign_channels`.

- [ ] **Step 1 (TDD lógica):** test de validación del form (no guarda sin `ends_at`) y del mapeo de los campos del brief a filas de `requirements` (tipo + `spec` por requisito elegido). Implementar.
- [ ] **Step 2 (visual):** usar `frontend-design` para el editor, el formulario del brief y el selector de canales.
- [ ] **Step 3: Commit** `feat: editor de campañas con brief manual, asignación y plazo`.

### Tarea 9: Dashboard

**Files:** `frontend/src/pages/DashboardPage.tsx`, test asociado.

**Especificación:**
- Tarjetas de resumen: total, al día (`verified`), requieren atención (`incomplete`/`review`), pendientes.
- Una fila por canal-campaña con su última publicación y el badge de estado vía `dashboardRowBadge(status, hasVideoInReview)` (Tarea 2): muestra los 5 estados (Cumple / Incompleto / En revisión / Pendiente / No cumplió), derivando "En revisión" del video.
- Clic en una fila → `videos/:id`.

- [ ] **Step 1 (TDD lógica):** test del cómputo de los contadores del resumen a partir de una lista de `campaign_channels`. Implementar una función pura `summarize(rows)` + render mínimo.
- [ ] **Step 2 (visual):** usar `frontend-design` para las tarjetas y la tabla.
- [ ] **Step 3: Commit** `feat: dashboard con resumen y filas por canal-campaña`.

### Tarea 10: Detalle de video

**Files:** `frontend/src/pages/VideoDetailPage.tsx`, test asociado.

**Especificación:**
- Para el video, mostrar el veredicto **por campaña** (un video puede tener varias `verifications`).
- Checklist de requisitos con su `RequirementResult`: cumplido/no, confianza, **cita de evidencia** y link al timestamp (`evidence_timestamp_s` → `https://youtu.be/<id>?t=<s>`).

- [ ] **Step 1 (TDD lógica):** test de la función que arma el link al timestamp (`youtubeTimestampUrl(videoId, seconds)`). Implementar.
- [ ] **Step 2 (visual):** usar `frontend-design` para la checklist y la evidencia.
- [ ] **Step 3: Commit** `feat: detalle de video con evidencia por campaña`.

### Tarea 11: Cola de revisión

**Files:** `frontend/src/pages/ReviewQueuePage.tsx`, `frontend/src/data/reviews.ts`, tests asociados.

**Especificación:**
- Lista de videos cuya verificación está en `review`, con link directo al video.
- Para `review` por R5: mensaje "todo el texto cumple, confirmá el gameplay".
- La persona decide (pass/fail, `confirmed_gameplay`) → insert en `reviews` por RLS (`reviewer_id = auth.uid()`).

- [ ] **Step 1 (TDD lógica):** test de `insertReview` (cliente mockeado) verificando el insert con `reviewer_id`. Implementar `reviews.ts`.
- [ ] **Step 2 (visual):** usar `frontend-design` para la cola y el panel de decisión.
- [ ] **Step 3: Commit** `feat: cola de revisión con decisión humana`.

---

## Validación de la fase (criterios de salida)

- [ ] `cd frontend && npm run test` pasa; `npm run build` compila sin errores de TS.
- [ ] Registrarse crea la organización personal automáticamente (trigger) y el usuario solo ve lo suyo (RLS).
- [ ] Importar un archivo de canales (parseado en el cliente) puebla la grilla por RLS; los no resueltos quedan marcados y el cron tick (Fase 3) los resuelve.
- [ ] Crear una campaña: completar el brief en el formulario → elegir requisitos → asignar canales → fijar plazo → guardar (todo por RLS).
- [ ] El dashboard muestra los estados correctos; la cola de revisión permite decidir y guarda en `reviews`.

## Notas / riesgos a confirmar al implementar

- **Sin backend en esta fase:** el frontend habla solo con Supabase (RLS). No hay JWT en backend, ni CORS, ni `VITE_BACKEND_URL`. La resolución de canales y el WebSub los maneja el cron tick (Fase 3).
- **Aislamiento multi-tenant:** las RLS del `schema.sql` ya garantizan que cada usuario vea solo su org. Verificar con dos usuarios distintos que no se filtran datos.
- **Protección de rutas:** envolver el router con `AuthProvider` y un guard que redirija a `LoginPage` si no hay sesión (no detallado acá por brevedad; es wiring directo).
- **Pulido visual:** todas las vistas usan el skill `frontend-design` para el diseño final; este plan fija la estructura, los datos y la lógica, no el estilo.
