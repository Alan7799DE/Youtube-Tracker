# Fase 4 — Interfaz web + multi-tenancy · Plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDO: usá `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkboxes (`- [ ]`) para tracking. Para el pulido visual de cada vista, usá el skill `frontend-design`.

**Goal:** una app web React multi-usuario donde cada persona se registra (con organización personal automática), importa canales, crea campañas con su brief, ve el estado de cada canal-campaña y resuelve la cola de revisión — leyendo de Supabase con RLS y delegando al backend las operaciones que necesitan secretos.

**Architecture:** frontend React + Vite + TypeScript que **lee** de Supabase con la *anon key* gobernada por RLS, y **escribe** la config sin efectos externos (campañas, requisitos, asignaciones, reviews) también vía RLS. Las operaciones con efectos externos o secretos —extracción del brief (LLM) y mutaciones de canales (resolución + WebSub)— pasan por una **API backend autenticada** (FastAPI) que reusa las funciones de las Fases 2–3. La organización personal se crea sola por el trigger del `schema.sql`.

**Tech Stack:** React 18, Vite, TypeScript, `@supabase/supabase-js` v2, `react-router-dom` v6, Vitest + `@testing-library/react` + jsdom. Backend: FastAPI + `pyjwt` (validación del JWT de Supabase). Pulido visual: skill `frontend-design`.

**Alcance (diseño, sección 15 · Fase 4 + sección 8):**
- **Entra:** auth + organización personal, app shell con los 4 menús, dashboard, detalle de video, gestión de campañas (brief con extracción LLM + confirmación, asignación de canales, plazo), grilla de importación de canales, cola de revisión. Multi-tenancy efectiva (RLS por org ya en el schema).
- **No entra:** notificaciones (Fase 5), robustez/escala (Fase 6). El cableado fino de resolución/WebSub vive en el backend (Fases 2–3) y se invoca desde la API.

**Prerrequisito:** Fases 1–3 implementadas; un proyecto Supabase con el `schema.sql` corrido; las API keys (OpenAI, YouTube) en el backend.

**Sobre el formato:** las tareas de **lógica** (mapeo de estados, auth, data layer, endpoints) van en TDD estricto con código real. Las tareas de **vistas visuales** dan una especificación concreta (datos, estados, acciones) + un test de lógica/smoke, y el armado visual fino se hace con el skill `frontend-design`. No usar placeholders en el código de lógica.

---

## Estructura de archivos

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  vitest.config.ts
  .env.example                 # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_BACKEND_URL
  src/
    lib/
      supabase.ts              # cliente supabase (anon)
      types.ts                 # tipos de las tablas del schema
      status.ts                # estado -> badge (label/tone)  [TDD]
      api.ts                   # llamadas a la API backend (brief extract, channels)
    auth/
      AuthProvider.tsx         # contexto de sesión (Supabase Auth)
      useAuth.ts
      LoginPage.tsx
    app/
      AppShell.tsx             # layout + barra lateral (4 menús + cuenta)
      router.tsx
    data/
      channels.ts              # queries RLS de canales
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

backend/
  verifier/api/
    __init__.py
    auth.py                    # JWT de Supabase -> org_id  [TDD]
    app.py                     # FastAPI: /api/brief/extract, /api/channels/import  [TDD]
  tests/
    test_api_auth.py
    test_api_app.py
```

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
    "react-router-dom": "^6.26.0"
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
VITE_BACKEND_URL=http://localhost:8000
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
import { channelStatusBadge } from "./status";

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
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `cd frontend && npx vitest run src/lib/status.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/status.ts frontend/src/lib/status.test.ts
git commit -m "feat: mapeo de estados a badges"
```

---

## Tarea 3: API backend autenticada (FastAPI)

Endpoints que el frontend invoca para lo que necesita secretos: extracción del brief (LLM) e importación de canales (resolución + WebSub). Autentica con el JWT de Supabase y deriva el `org_id` del usuario.

**Files:**
- Create: `backend/verifier/api/__init__.py`, `backend/verifier/api/auth.py`, `backend/verifier/api/app.py`
- Test: `backend/tests/test_api_auth.py`, `backend/tests/test_api_app.py`
- Modify: `backend/pyproject.toml` (agregar `pyjwt>=2.8`)

- [ ] **Step 1: Agregar dep `pyjwt` y crear `__init__.py`**

En `backend/pyproject.toml` `dependencies`: `"pyjwt>=2.8",`. Crear `backend/verifier/api/__init__.py` vacío. Instalar: `cd backend && . .venv/bin/activate && pip install -e ".[dev]"`.

- [ ] **Step 2: Escribir el test de auth que falla**

```python
import jwt
import pytest
from verifier.api.auth import user_id_from_token

SECRET = "test-secret"


def test_decodes_valid_token():
    token = jwt.encode({"sub": "user-123"}, SECRET, algorithm="HS256")
    assert user_id_from_token(token, secret=SECRET) == "user-123"


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        user_id_from_token("garbage", secret=SECRET)
```

- [ ] **Step 3: Implementar `backend/verifier/api/auth.py`**

```python
from __future__ import annotations
import jwt


def user_id_from_token(token: str, *, secret: str) -> str:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError as exc:
        raise ValueError("token inválido") from exc
    sub = payload.get("sub")
    if not sub:
        raise ValueError("token sin sub")
    return sub
```

- [ ] **Step 4: Correr el test de auth**

Run: `pytest tests/test_api_auth.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Escribir el test de la app que falla**

```python
import jwt
from fastapi.testclient import TestClient
from verifier.api import app as appmod

SECRET = "test-secret"


def _token(user="u1"):
    return jwt.encode({"sub": user}, SECRET, algorithm="HS256")


def test_brief_extract_requires_auth():
    client = TestClient(appmod.app)
    resp = client.post("/api/brief/extract", json={"text": "x"})
    assert resp.status_code == 401


def test_brief_extract_returns_draft(monkeypatch):
    monkeypatch.setattr(appmod, "JWT_SECRET", SECRET)
    monkeypatch.setattr(appmod, "org_for_user", lambda uid: "org-1")
    monkeypatch.setattr(
        appmod, "extract_brief_text",
        lambda text, org_id: {"game_name": "G", "requirements": []},
    )
    client = TestClient(appmod.app)
    resp = client.post(
        "/api/brief/extract",
        json={"text": "Promociona G"},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert resp.status_code == 200
    assert resp.json()["game_name"] == "G"
```

- [ ] **Step 6: Implementar `backend/verifier/api/app.py`**

```python
from __future__ import annotations
import os
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from verifier.api.auth import user_id_from_token
from verifier.brief.extract import extract_brief

app = FastAPI()
JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")


def org_for_user(user_id: str) -> Optional[str]:
    """Reemplazable: busca el org_id del usuario (organization_members) con service_role.
    Se monkeypatcha en tests; en producción consulta Supabase."""
    return None


def extract_brief_text(text: str, org_id: str) -> dict:
    """Reemplazable: corre la extracción LLM. Se monkeypatcha en tests."""
    client = OpenAI()
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    return extract_brief(text, client=client, model=model).model_dump()


def _require_org(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="falta token")
    token = authorization.split(" ", 1)[1]
    try:
        user_id = user_id_from_token(token, secret=JWT_SECRET)
    except ValueError:
        raise HTTPException(status_code=401, detail="token inválido")
    org_id = org_for_user(user_id)
    if org_id is None:
        raise HTTPException(status_code=403, detail="usuario sin organización")
    return org_id


class BriefExtractRequest(BaseModel):
    text: str


@app.post("/api/brief/extract")
def brief_extract(body: BriefExtractRequest, authorization: Optional[str] = Header(default=None)) -> dict:
    org_id = _require_org(authorization)
    return extract_brief_text(body.text, org_id)
```

> Nota: el endpoint de importación de canales (`POST /api/channels/import`) sigue el mismo patrón de auth y delega en `parse_channels_file` + `reconcile` + resolución/suscripción (Fases 2–3) usando el `org_id`; su cableado contra Supabase es integración. Se construye igual que `brief_extract`: `_require_org` → función reemplazable inyectada. Agregar su test análogo a `test_brief_extract_returns_draft`.

- [ ] **Step 7: Correr los tests de la app**

Run: `pytest tests/test_api_app.py -v`
Expected: PASS (2 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/verifier/api/ backend/tests/test_api_auth.py backend/tests/test_api_app.py backend/pyproject.toml
git commit -m "feat: API backend autenticada (brief extract) con JWT de Supabase"
```

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
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("muestra los 4 menús principales", () => {
    render(<MemoryRouter><AppShell /></MemoryRouter>);
    for (const label of ["Dashboard", "Campañas", "Canales", "Revisión"]) {
      expect(screen.getByRole("link", { name: label })).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `cd frontend && npx vitest run src/app/AppShell.test.tsx`
Expected: FAIL (no existe `AppShell`).

- [ ] **Step 3: Implementar `frontend/src/app/AppShell.tsx`**

```tsx
import { Link, Outlet } from "react-router-dom";

const MENUS = [
  { to: "/", label: "Dashboard" },
  { to: "/campaigns", label: "Campañas" },
  { to: "/channels", label: "Canales" },
  { to: "/review", label: "Revisión" },
];

export function AppShell() {
  return (
    <div style={{ display: "flex" }}>
      <nav aria-label="principal">
        <ul>
          {MENUS.map((m) => (
            <li key={m.to}><Link to={m.to}>{m.label}</Link></li>
          ))}
        </ul>
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
- Botón "Importar archivo" (CSV/`.xlsx`): sube el archivo a `POST /api/channels/import` (Tarea 3) → la API parsea, reconcilia, resuelve y suscribe; al volver, se refresca la grilla.
- Sección destacada de canales **no resueltos** (`resolution_status='unresolved'`) para corregir a mano.
- Reemplazo total: subir un archivo reemplaza el conjunto activo (la API hace la reconciliación con soft-deactivate; ver Fase 2).

- [ ] **Step 1 (TDD lógica):** test de `ChannelsPage` que, con `listChannels` mockeado, renderiza una fila por canal y resalta los `unresolved`. Implementar el componente para que pase.
- [ ] **Step 2 (visual):** usar `frontend-design` para la grilla, el botón de import y la sección de no resueltos.
- [ ] **Step 3: Commit** `feat: página de canales (grilla + importación)`.

### Tarea 8: Editor de campañas (brief + asignación + plazo)

**Files:** `frontend/src/pages/CampaignsPage.tsx`, `frontend/src/pages/CampaignEditor.tsx`, tests asociados.

**Especificación:**
- `CampaignsPage`: lista de campañas con su estado; botón "Nueva campaña"; "Cerrar" (no borrar) una campaña → `status='closed'`.
- `CampaignEditor`: form con marca, nombre y **plazo (`ends_at` obligatorio**, validar antes de guardar).
- Brief: subir `.txt`/`.docx` o pegar texto → llamar `POST /api/brief/extract` → mostrar el **formulario pre-cargado y editable** con los requisitos extraídos → el usuario **elige qué requisitos verificar** y **confirma** antes de guardar (insert en `campaigns`/`requirements` por RLS).
- Asignar canales: multiselección de canales de la org → filas en `campaign_channels`.

- [ ] **Step 1 (TDD lógica):** test de validación del form (no guarda sin `ends_at`) y del mapeo del draft del brief a filas de `requirements`. Implementar.
- [ ] **Step 2 (visual):** usar `frontend-design` para el editor, el flujo de brief (upload → confirmar) y el selector de canales.
- [ ] **Step 3: Commit** `feat: editor de campañas con brief, asignación y plazo`.

### Tarea 9: Dashboard

**Files:** `frontend/src/pages/DashboardPage.tsx`, test asociado.

**Especificación:**
- Tarjetas de resumen: total, al día (`verified`), requieren atención (`incomplete`/`review`), pendientes.
- Una fila por canal-campaña con su última publicación y el badge de estado (`channelStatusBadge`, Tarea 2). Para videos en `review`, mostrar ese estado (derivado del video).
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
- [ ] `cd backend && pytest -q` pasa (incluye los tests de la API).
- [ ] Registrarse crea la organización personal automáticamente (trigger) y el usuario solo ve lo suyo (RLS).
- [ ] Importar un archivo de canales puebla la grilla; los no resueltos quedan marcados.
- [ ] Crear una campaña: subir brief → confirmar requisitos → asignar canales → fijar plazo → guardar.
- [ ] El dashboard muestra los estados correctos; la cola de revisión permite decidir y guarda en `reviews`.

## Notas / riesgos a confirmar al implementar

- **Aislamiento multi-tenant:** las RLS del `schema.sql` ya garantizan que cada usuario vea solo su org. Verificar con dos usuarios distintos que no se filtran datos.
- **JWT de Supabase:** el secreto para validar el token en el backend (`SUPABASE_JWT_SECRET`) sale del proyecto Supabase. Si el proyecto usa claves asimétricas (JWKS), ajustar `auth.py` para validar con la clave pública en vez de HS256.
- **Protección de rutas:** envolver el router con `AuthProvider` y un guard que redirija a `LoginPage` si no hay sesión (no detallado acá por brevedad; es wiring directo).
- **Pulido visual:** todas las vistas usan el skill `frontend-design` para el diseño final; este plan fija la estructura, los datos y la lógica, no el estilo.
- **CORS:** el backend (FastAPI) debe permitir el origen del frontend para las llamadas a `/api/*`.
