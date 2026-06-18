# Requisitos y arquitectura de despliegue

> Documento vivo. Define **cómo y dónde corre el sistema en producción**, qué hay que tener del lado de la infraestructura, y los archivos a crear cuando se materialice el despliegue. Complementa a [`requisitos-externos.md`](requisitos-externos.md) (cuentas y claves).

## Dónde corre

- **Backend (callback de WebSub + cron tick):** un **VPS de Hostinger** (siempre encendido, con URL pública e ingreso HTTPS). Se empaqueta con **Docker** para subirlo y actualizarlo fácil. **No expone API autenticada** — su única superficie HTTP es el callback de WebSub.
- **Frontend (React):** se construye estático (`npm run build`) y se **sirve desde el mismo VPS con Caddy**. Habla **solo con Supabase** (lee y escribe config por RLS); no llama al backend. **Vercel/Netlify queda como alternativa opcional**.

## Cuándo se materializa

El despliegue **no se necesita hasta la Fase 3**: las Fases 1 y 2 corren local (CLI y funciones con tests). En la **Fase 3**, WebSub necesita un endpoint público que el hub de YouTube pueda alcanzar → ahí la app tiene que vivir en el VPS. Por eso este doc se ejecuta como un paso de la Fase 3 (un "Fase 3.5 / Deploy").

## Arquitectura de despliegue (Docker Compose en el VPS)

```
   navegador                         hub de YouTube
      │ (frontend, estático)              │ POST /websub/callback
      ▼                                    ▼  443
  ┌─────────────────────────── caddy ───────────────────────────┐
  │  HTTPS automático (Let's Encrypt): sirve el frontend en /     │
  │  y hace proxy de /websub/callback → api                       │
  └───────────────┬───────────────────────────┬─────────────────┘
                  │ (estáticos)                │
                  ▼                            ▼
            frontend build            api (uvicorn): SOLO /websub/callback
                  │                            │
   cron del VPS ──┼──► python -m verifier.jobs.tick   (resolución + backoff + leases + plazos)
                  │                            │
                  ▼                            ▼
                       Supabase (Postgres + Auth + RLS)
   (el frontend le pega directo por RLS; el backend escribe con service_role)
```

- **Servicio `caddy`** — HTTPS automático. **Sirve el frontend estático** (en `/`) y hace de reverse proxy del **callback de WebSub** (`/websub/callback`) hacia `api`. Un solo dominio.
- **Servicio `api`** — un proceso uvicorn que sirve **únicamente el callback público de WebSub** (sin auth). No hay rutas `/api/*` (la config la escribe el frontend por RLS).
- **Cron tick** — un **único** job programado del VPS (`python -m verifier.jobs.tick`) que en cada corrida resuelve canales `unresolved` (+ suscribe WebSub), renueva leases por expirar, reintenta transcripts vencidos y marca incumplimientos por plazo. No expone puertos.
- **Frontend** — build estático servido por Caddy. Habla solo con Supabase (RLS). **No usa `VITE_BACKEND_URL` ni CORS**, porque no llama al backend.

## Entrypoint del backend

Como el backend solo expone el callback de WebSub, el target de uvicorn es directamente la app de WebSub:

```python
# backend/verifier/server.py
from verifier.websub.app import app  # FastAPI con solo el router de WebSub
# uvicorn verifier.server:app
```

> Al no haber API autenticada, no hace falta componer routers, ni JWT, ni middleware de CORS. El frontend nunca toca el backend.

## Archivos a crear (en el paso de deploy, ~Fase 3)

| Archivo | Para qué |
|---|---|
| `backend/Dockerfile` | Imagen del backend (Python 3.12 + deps + paquete `verifier`). |
| `backend/.dockerignore` | Excluir `.venv`, `__pycache__`, `.env`, tests del build. |
| `docker-compose.yml` | Servicios `api` + `caddy` (+ red + volúmenes de certificados y del build del frontend). |
| `Caddyfile` | HTTPS automático: sirve el frontend en `/` y proxea `/websub/callback` → `api`. |
| `backend/verifier/server.py` | Entrypoint ASGI (la app de WebSub). |
| `backend/verifier/jobs/tick.py` | El cron tick: orquesta resolución + backoff + leases + plazos. |

> Flujo de deploy: `git pull && docker compose up -d --build` en el VPS (o un GitHub Actions que haga SSH + ese comando). Los secretos viven en un `.env` del VPS (no en el repo); ver variables en [`requisitos-externos.md`](requisitos-externos.md).

## Checklist de requisitos de infraestructura (lado del usuario)

- [ ] **Acceso SSH al VPS** de Hostinger.
- [ ] **Docker + Docker Compose** instalados en el VPS.
- [ ] **Dominio o subdominio** apuntando a la IP del VPS (ej. `tudominio.com`).
- [ ] **Puertos 80 y 443 abiertos** en el firewall del VPS (Caddy los usa para HTTPS).
- [ ] **`.env` en el VPS** con las claves del backend (OpenAI, YouTube, Supabase URL/service_role) + `WEBSUB_CALLBACK_URL` (= `https://tudominio.com/websub/callback`).
- [ ] **Cron** configurado en el VPS para correr `python -m verifier.jobs.tick` cada pocos minutos.

## Variables de entorno adicionales (despliegue)

| Variable | Para qué | Dónde |
|---|---|---|
| `WEBSUB_CALLBACK_URL` | URL pública del callback (dominio + `/websub/callback`) | `backend/.env` |

> Ya **no** hacen falta `FRONTEND_ORIGIN` (no hay CORS) ni `VITE_BACKEND_URL` (el frontend no llama al backend). El resto de las claves está en [`requisitos-externos.md`](requisitos-externos.md).
