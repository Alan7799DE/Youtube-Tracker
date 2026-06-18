# Requisitos y arquitectura de despliegue

> Documento vivo. Define **cómo y dónde corre el sistema en producción**, qué hay que tener del lado de la infraestructura, y los archivos a crear cuando se materialice el despliegue. Complementa a [`requisitos-externos.md`](requisitos-externos.md) (cuentas y claves).

## Dónde corre

- **Backend (API + WebSub + jobs):** un **VPS de Hostinger** (siempre encendido, con URL pública e ingreso HTTPS). Se empaqueta con **Docker** para subirlo y actualizarlo fácil.
- **Frontend (React):** se construye estático (`npm run build`) y se **sirve desde el mismo VPS con Caddy** (recomendado: un solo servidor, mismo dominio → sin CORS, sin sumar otro servicio). **Vercel/Netlify queda como alternativa opcional** si más adelante querés CDN global o preview deploys.

## Cuándo se materializa

El despliegue **no se necesita hasta la Fase 3**: las Fases 1 y 2 corren local (CLI y funciones con tests). En la **Fase 3**, WebSub necesita un endpoint público que el hub de YouTube pueda alcanzar → ahí la app tiene que vivir en el VPS. Por eso este doc se ejecuta como un paso de la Fase 3 (un "Fase 3.5 / Deploy").

## Arquitectura de despliegue (Docker Compose en el VPS)

```
                    Internet (hub de YouTube + navegador → API)
                                   │  443
                          ┌────────▼─────────┐
                          │      caddy        │  reverse proxy + HTTPS automático (Let's Encrypt)
                          └───┬───────────┬───┘
                              │           │
                   ┌──────────▼──┐   ┌────▼──────────────┐
                   │  frontend   │   │       api          │  uvicorn (FastAPI):
                   │ (estático)  │   │ /websub/callback   │  /websub/callback + /api/*
                   └─────────────┘   └────────────────────┘
   cron del VPS ──► python -m verifier.jobs.run <job>   (backoff transcript, leases, revisor de plazos)
                          (no exponen puertos; corren y terminan)
                                   │
                                   ▼
                               Supabase (Postgres + Auth)  ── el frontend le pega directo por RLS
```

- **Servicio `caddy`** — reverse proxy con **HTTPS automático**. Resuelve el TLS del callback de WebSub y de la API. Se le apunta un subdominio (ej. `api.tudominio.com`).
- **Servicio `api`** — un único proceso uvicorn que sirve **el callback público de WebSub** (`/websub/callback`, sin auth) **y la API autenticada** (`/api/*`, con JWT). Ver "Entrypoint único" abajo.
- **Jobs programados** — el worker de transcript (backoff), la renovación de leases y el revisor de plazos corren como **cron del VPS** que invoca entrypoints del paquete (`python -m verifier.jobs.run ...`). No reciben requests, no exponen puertos.
- **Frontend** — build estático servido por **Caddy desde el VPS** (le pega a Supabase por RLS y a la API por `VITE_BACKEND_URL`). Si se sirve bajo el mismo dominio que la API, **no hace falta CORS**. Opcional: hostearlo en un static host externo (Vercel/Netlify).

## Entrypoint único (consistencia con las Fases 3 y 4)

Las Fases 3 y 4 definen routers FastAPI por separado (WebSub y API autenticada). En producción **se sirven desde una sola app ASGI**: `verifier/server.py` crea un `FastAPI()` y hace `include_router()` de ambos. Es el target de uvicorn en el contenedor:

```python
# backend/verifier/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from verifier.websub.app import router as websub_router
from verifier.api.app import router as api_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[__import__("os").environ.get("FRONTEND_ORIGIN", "*")],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(websub_router)
app.include_router(api_router)
```

> Por eso los planes de Fase 3 y Fase 4 exponen `router` (APIRouter) además de un `app` para testear cada módulo en aislamiento. El `server.py` los compone.

## Archivos a crear (en el paso de deploy, ~Fase 3)

| Archivo | Para qué |
|---|---|
| `backend/Dockerfile` | Imagen del backend (Python 3.12 + deps + paquete `verifier`). |
| `backend/.dockerignore` | Excluir `.venv`, `__pycache__`, `.env`, tests del build. |
| `docker-compose.yml` | Servicios `api` + `caddy` (+ red + volúmenes de certificados). |
| `Caddyfile` | HTTPS automático: sirve el **frontend estático** y hace de reverse proxy de `/api/*` y `/websub/*` hacia `api`. |
| `backend/verifier/server.py` | Entrypoint ASGI único (routers WebSub + API). |
| `backend/verifier/jobs/run.py` | CLI para que el cron invoque cada job. |

> Flujo de deploy: `git pull && docker compose up -d --build` en el VPS (o un GitHub Actions que haga SSH + ese comando). Los secretos viven en un `.env` del VPS (no en el repo); ver variables en [`requisitos-externos.md`](requisitos-externos.md).

## Checklist de requisitos de infraestructura (lado del usuario)

- [ ] **Acceso SSH al VPS** de Hostinger.
- [ ] **Docker + Docker Compose** instalados en el VPS.
- [ ] **Dominio o subdominio** apuntando a la IP del VPS (ej. `api.tudominio.com` para el backend).
- [ ] **Puertos 80 y 443 abiertos** en el firewall del VPS (Caddy los usa para HTTPS).
- [ ] **`.env` en el VPS** con las claves del backend (OpenAI, YouTube, Supabase URL/service_role/JWT) + `FRONTEND_ORIGIN` y `WEBSUB_CALLBACK_URL` (= `https://api.tudominio.com/websub/callback`).
- [ ] **(Frontend) servido por Caddy desde el VPS** — el build (`npm run build`) se copia al server y Caddy lo sirve. Opcional: cuenta de Vercel/Netlify si preferís hostearlo afuera.

## Variables de entorno adicionales (despliegue)

| Variable | Para qué | Dónde |
|---|---|---|
| `FRONTEND_ORIGIN` | CORS: origen del frontend. **Solo si está en otro dominio** (Vercel/subdominio distinto); sirviendo desde el mismo dominio que la API, no hace falta. | `backend/.env` |
| `WEBSUB_CALLBACK_URL` | URL pública del callback (dominio + `/websub/callback`) | `backend/.env` |

(El resto de las claves del backend y del frontend están en [`requisitos-externos.md`](requisitos-externos.md).)
