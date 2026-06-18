# Requisitos externos (setup del lado del usuario)

> Documento vivo. Lista las cuentas, claves y servicios que **aporta el usuario** (no se pueden crear desde el código): se van tildando a medida que se consiguen, agrupados por la fase en la que se necesitan. El código, los `.env.example` y la guía paso a paso los pone Claude.

**Regla de seguridad:** todas las claves van en archivos `.env` (que están en `.gitignore`). **Nunca** se commitean al repo. Acá solo se documenta *qué* se necesita y *dónde* va, no el valor.

---

## 🟢 Fase 1 — Núcleo de verificación (para arrancar ya)

Corre **local** (máquina del usuario, IP residencial). No necesita Supabase todavía.

- [ ] **API key de OpenAI** — [platform.openai.com](https://platform.openai.com) → API keys. Requiere **billing activado** (pago por uso, no es ChatGPT Plus). → `backend/.env`: `OPENAI_API_KEY`
- [ ] **API key de YouTube Data API v3** — [console.cloud.google.com](https://console.cloud.google.com): crear proyecto → habilitar "YouTube Data API v3" → Credenciales → API key. → `backend/.env`: `YOUTUBE_API_KEY`
- [ ] **Modelo de LLM** (decisión) — por defecto `gpt-4o-mini`. → `backend/.env`: `LLM_MODEL`
- [ ] **Set dorado** — 30–50 videos reales etiquetados a mano (cumple/no cumple por requisito). Trabajo del equipo, no técnico. Se puede arrancar con 5–10. → `backend/golden/`
- [ ] **Datos de prueba** — un brief de ejemplo + un par de URLs de video reales para probar el CLI.

---

## 🟡 Fases 2–3 — Resolución de canales y detección (WebSub)

- [ ] **Proyecto de Supabase** — [supabase.com](https://supabase.com) → crear proyecto.
- [ ] **Correr `schema.sql`** en el SQL Editor de Supabase (crea las 14 tablas + RLS + triggers).
- [ ] **Project URL de Supabase** (Settings → API). → `backend/.env`: `SUPABASE_URL` · `frontend/.env`: `VITE_SUPABASE_URL`
- [ ] **`service_role` key de Supabase** (Settings → API) — secreta, solo backend. → `backend/.env`: `SUPABASE_SERVICE_ROLE_KEY`
- [ ] **Endpoint público para WebSub** — el callback debe ser accesible desde internet con HTTPS. Local: **ngrok** (`ngrok http 8000`). Producción: backend desplegado. → `backend/.env`: `WEBSUB_CALLBACK_URL`

---

## 🔵 Fase 4 — Interfaz web + multi-tenancy

> El frontend habla **solo con Supabase** (no hay API backend), así que no hacen falta JWT en el backend, CORS ni `VITE_BACKEND_URL`.

- [ ] **`anon` key de Supabase** (Settings → API) — para el frontend. → `frontend/.env`: `VITE_SUPABASE_ANON_KEY`
- [ ] **Habilitar Email Auth** en Supabase (Authentication → Providers → Email). Para testear rápido se puede desactivar la confirmación por email.

---

## ⚪ Despliegue (cuando se salga de local)

- [ ] **Hosting del frontend** — servido desde el **VPS con Caddy** (recomendado; mismo dominio que la API → sin CORS). Vercel/Netlify queda como opcional.
- [ ] **Hosting del backend** — **VPS de Hostinger** (ya disponible), con Docker + URL pública + TLS para el WebSub.

> El **cómo** del despliegue (Docker, Caddy, cron tick, checklist de infraestructura) está en [`requisitos-despliegue.md`](requisitos-despliegue.md).

---

## Resumen de variables de entorno

### `backend/.env`
| Variable | Para qué | Fase |
|---|---|---|
| `OPENAI_API_KEY` | LLM de **verificación** (R3/R4) | 1 |
| `YOUTUBE_API_KEY` | Metadata + resolución de canales | 1 |
| `LLM_MODEL` | Modelo a usar (def. `gpt-4o-mini`) | 1 |
| `SUPABASE_URL` | Conexión a la base | 2 |
| `SUPABASE_SERVICE_ROLE_KEY` | Escritura backend (bypassea RLS) | 2 |
| `WEBSUB_CALLBACK_URL` | Callback público de WebSub | 3 |

### `frontend/.env`
| Variable | Para qué | Fase |
|---|---|---|
| `VITE_SUPABASE_URL` | Conexión a la base (lectura/escritura por RLS) | 4 |
| `VITE_SUPABASE_ANON_KEY` | Cliente Supabase del frontend | 4 |

> El frontend no tiene `VITE_BACKEND_URL` porque no llama al backend; toda la config la escribe por RLS contra Supabase.

---

## Qué hace cada parte

- **El usuario:** crea cuentas, activa billing, genera las claves, corre el `schema.sql`, arma el set dorado y pega las claves en los `.env`.
- **Claude:** escribe todo el código, los `.env.example`, y guía paso a paso dónde clickear en cada dashboard.
