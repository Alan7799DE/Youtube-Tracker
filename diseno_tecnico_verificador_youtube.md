# Documento de diseño técnico — Verificador de publicidad en YouTube (v3)

> Sistema que toma una lista de canales desde un Google Doc, detecta automáticamente cuándo esos influencers suben videos, y verifica si cumplen los requisitos publicitarios acordados. Reemplaza la revisión manual perfil por perfil (incluso fines de semana) por un monitoreo automático con una interfaz web donde se ve el estado de cada canal.

---

## 1. Objetivo y alcance

**Problema:** hoy la verificación es manual, perfil por perfil, incluso fines de semana.

**Objetivo:** que el sistema sepa qué canales monitorear (desde un Google Doc), detecte las subidas en tiempo real, verifique solo los requisitos automatizables con alta confianza, derive a una persona únicamente los casos ambiguos, y muestre todo en una interfaz web.

### Requisitos a verificar (caso real)

| # | Requisito | Dónde vive | Método de verificación | v1 |
|---|---|---|---|---|
| R1 | Link de descarga en la descripción | Texto | Determinístico (match exacto) | ✅ |
| R2 | Código promocional en la descripción | Texto | Determinístico (match exacto) | ✅ |
| R3 | Menciona el nombre del juego en el video | Audio | LLM sobre transcript | ✅ |
| R4 | Habla de qué trata el juego | Audio | LLM sobre transcript | ✅ |
| R5 | Muestra gameplay del juego en pantalla | Visual | Humano (v1) / visión (v2) | ⚠️ humano |

**Principio de diseño clave:** R1–R4 cubren ~90% del valor sin tocar un solo frame de video. R5 es el único que necesita revisión humana en v1. El link y el código, aunque se acuerde mostrarlos en pantalla, también van en la descripción y casi siempre se dicen en voz alta, así que se verifica su *existencia* por texto/audio.

### Fuera de alcance v1
- Verificación visual automática (detección de gameplay, OCR de link/código en pantalla).
- Proxies residenciales / anti-bloqueo de transcript (se evalúa más adelante; ver sección 5.2).
- Plataformas que no sean YouTube.

---

## 2. Arquitectura general

Cuatro responsabilidades separadas:

1. **Entrada** — saber qué canales monitorear, leyendo un Google Doc (fuente de verdad).
2. **Detección** — saber cuándo hay un video nuevo, vía push de YouTube (WebSub).
3. **Ingesta + verificación** — obtener metadata y transcript, y comparar contra el brief produciendo un veredicto estructurado y auditable.
4. **Presentación** — una interfaz web que muestra el estado de cada canal y su última publicación.

Las partes pesadas (transcripción, razonamiento del LLM) se delegan a servicios externos vía API. La persistencia y la integración entre componentes viven en Supabase (Postgres), que actúa como contrato compartido entre el backend y la interfaz.

---

## 3. Entrada: lista de canales desde Google Docs

La lista de canales a monitorear vive en un Google Doc que mantiene el equipo. El sistema lo lee y lo trata como **fuente de verdad**: lo que está en el doc es lo que se monitorea.

### 3.1 Resolución de canal (nombre → channel_id)

El doc trae *nombres* de canales, pero la detección por WebSub necesita el `channel_id` (un identificador interno tipo `UC...`). Y los nombres no son únicos: puede haber varios "GamerPro". Por eso hay un paso de **resolución**: por cada entrada del doc, resolver nombre → `channel_id` con la YouTube Data API (`search` o `channels.list` con `forHandle`).

**Recomendación operativa:** pedir que en el Google Doc se carguen **handles (`@gamerpro`) o URLs de canal**, no nombres sueltos. Con handle o URL la resolución es exacta. Si solo hay un nombre ambiguo, el canal queda en estado "no resuelto" y aparece en la vista de configuración para confirmarlo a mano.

### 3.2 Lectura del Google Doc

Se lee con la Google Docs API (o Drive API) autenticándose contra la cuenta de Google del equipo. A diferencia de los subtítulos de YouTube, acá el OAuth **sí** es válido: el doc es propiedad del equipo, así que autorizar el acceso es directo.

### 3.3 Modelo de sincronización

Un job lee el doc periódicamente (o cuando alguien aprieta "re-sincronizar" en la UI), compara la lista actual contra los canales ya registrados, y reconcilia:
- Canales nuevos → se resuelven y se suscriben al WebSub.
- Canales que desaparecieron del doc → se desuscriben.

El Google Doc es la fuente de verdad; la base solo refleja ese estado. El ID del documento a leer se guarda en la tabla `app_settings` (`key = 'google_doc'`), y cada corrida queda registrada en `sync_runs`.

---

## 4. Detección: YouTube WebSub (push, no polling)

YouTube expone notificaciones push vía **WebSub (PubSubHubbub)**. En vez de consultar cada canal cada X minutos (caro en quota y con latencia), te suscribís una vez por canal y YouTube te avisa.

**Mecánica:**
- **Hub:** `https://pubsubhubbub.appspot.com/subscribe`
- **Topic (feed del canal):** `https://www.youtube.com/xml/feeds/videos.xml?channel_id={CHANNEL_ID}`
- Te suscribís con un POST al hub: `hub.callback` (tu endpoint público), `hub.topic`, `hub.mode=subscribe` y opcionalmente `hub.secret`.
- El hub confirma con un GET a tu callback que incluye `hub.challenge`: devolvés ese valor tal cual para validar.
- Ante una subida, el hub hace un POST a tu callback con un feed Atom XML que trae `videoId` y `channelId`.

**Cuidados importantes:**
- **Lease:** la suscripción expira (máx. ~10 días). Necesitás un job que renueve las suscripciones activas.
- **Duplicados y updates:** el feed también dispara cuando se edita título/descripción, no solo en la subida. Deduplicar por `videoId`.
- **Verificación de firma:** si usás `hub.secret`, validá el HMAC del cuerpo (`X-Hub-Signature`).
- **Endpoint público:** el callback tiene que ser accesible desde internet.

> Confirmá los detalles del topic/hub contra la documentación vigente de YouTube antes de implementar.

---

## 5. Ingesta de datos

### 5.1 Metadata (fácil y confiable)

`videos.list` de la YouTube Data API v3 con `part=snippet,contentDetails`:
- `snippet.title`, `snippet.description` → de acá salen R1 y R2.
- `snippet.channelId`, `snippet.publishedAt`, `contentDetails.duration`.

Costo: 1 unidad de quota por llamada (quota default ~10.000/día). Más que suficiente.

### 5.2 Transcript: librería, confiabilidad y decisión de v1

**Librería elegida:** `youtube-transcript-api` de Jonas Depoix.
- Repo: https://github.com/jdepoix/youtube-transcript-api
- PyPI: https://pypi.org/project/youtube-transcript-api/
- Licencia **MIT** (uso comercial libre), proyecto mantenido y muy usado (~6.5k stars).
- Funciona con subtítulos auto-generados, no requiere API key ni navegador headless.

**El problema de confiabilidad (importante):** YouTube bloquea la mayoría de las IPs de proveedores cloud (AWS, GCP, Azure). Al desplegar en un servidor cloud es muy probable recibir errores `RequestBlocked` / `IpBlocked`. Una IP self-hosted también puede ser baneada si hace demasiados requests. La solución robusta que recomienda el autor es usar **proxies residenciales rotativos** (integró Webshare para facilitarlo), porque YouTube banea los proxies estáticos tras uso prolongado.

**Decisión para v1:** usar **solo la librería, sin proxies**. Se acepta el riesgo de bloqueos. Si el producto muestra tracción/mercado, recién ahí se suma un servicio de proxies residenciales o se migra a una API de transcript de terceros que ya resuelva el bloqueo.

**Implicancias honestas de esta decisión:**
- Corriendo desde una IP residencial (desarrollo/validación local) la librería anda bien.
- En un servidor cloud, esperá bloqueos intermitentes. Como el volumen es bajo (~24 canales, pocas subidas), el riesgo se reduce, pero el bloqueo es por rango de IP, no solo por volumen: puede pasar igual.
- Los videos cuyo transcript no se pueda obtener caen, tras agotar reintentos, a **revisión humana** (no rompen el sistema).

**Alternativas futuras (cuando haya mercado):**
- (A) `youtube-transcript-api` + proveedor de proxies residenciales (~US$5–15/mes según volumen).
- (B) API de transcript de terceros (servicios tipo TranscriptAPI.com) que ya manejan el bloqueo; menos mantenimiento a cambio de un costo por uso.

**Decisión técnica de diseño:** abstraé la transcripción detrás de una interfaz (`TranscriptProvider`) para poder pasar de "solo librería" a "librería + proxies" o "API de terceros" sin tocar el resto del sistema.

```python
class TranscriptProvider(Protocol):
    def get_transcript(self, video_id: str) -> Transcript | None: ...
    # Transcript = lista de segmentos {text, start, duration}
```

### 5.3 Sobre el contenido del transcript: NO requiere procesamiento

Aclaración importante para no sobredimensionar la complejidad: el *contenido* del transcript no necesita NLP ni análisis. El flujo es simplemente **descargar → guardar en Supabase → pasar a la LLM** junto con el brief.

La única transformación es trivial: la librería devuelve segmentos con tiempos `[{text, start, duration}, ...]`. Se los une en un solo texto antes de mandarlos. Si se quiere que la LLM devuelva timestamps como evidencia, se conservan los tiempos y se formatea como `[00:01] texto...`. Es un `join`, no "procesamiento".

**No se necesita RAG, embeddings ni base vectorial.** El transcript de un video entero entra cómodo en el contexto del modelo (incluso ~1 h ≈ ~12.000 tokens, muy por debajo del límite), así que se manda completo en un solo prompt. Toda la dificultad del transcript está en *obtenerlo* (sección 5.2), no en qué se hace con él.

### 5.4 Disponibilidad diferida del transcript (crítico para el diseño)

Los subtítulos automáticos **no están disponibles en el instante en que se publica el video**. YouTube los procesa entre minutos y varias horas después, y los videos más largos tardan más. A veces publica primero un borrador con más errores y lo reemplaza por una versión pulida en los 30 min a pocas horas siguientes.

Esto choca con el WebSub: la notificación llega *cuando se publica*, momento en que el transcript todavía no existe o está en borrador. **Conclusión de diseño:** desacoplar el evento "video detectado" del evento "video listo para verificar".

**Patrón de reintento con backoff.** Al llegar el WebSub, NO se transcribe de inmediato. El video entra en espera y un worker reintenta obtener el transcript con backoff creciente hasta que aparezca estable.

```python
BACKOFF_SCHEDULE_MIN = [15, 30, 60, 120, 240, 480]  # min desde la detección
MAX_WAIT_HOURS = 24

def attempt_transcript(video):
    transcript = provider.get_transcript(video.youtube_video_id)
    if transcript is None:
        if elapsed_hours(video.detected_at) >= MAX_WAIT_HOURS:
            video.status = "needs_human"      # se agotó el backoff
        else:
            video.status = "awaiting_transcript"
            video.next_retry_at = next_backoff(video.transcript_attempts)
            video.transcript_attempts += 1
        return
    video.status = "verifying"               # transcript estable -> a verificar
    enqueue_verification(video, transcript)
```

**Casos borde:** sin transcript tras 24 h (creador desactivó subtítulos) → `needs_human`; Shorts/videos muy cortos pueden ser inconsistentes → mismo destino; creadores grandes que suben sus propios subtítulos → disponibles desde el minuto cero.

### 5.5 Máquina de estados del video

```
detected ──► awaiting_transcript ──► verifying ──► resolved (pass | fail | review)
                  │  ▲
                  │  └── reintento (transcript aún no disponible)
                  │
                  └── timeout 24 h ──► needs_human
```

| Estado | Significado | Transición de salida |
|---|---|---|
| `detected` | Llegó el WebSub, video registrado | Encola primer intento de transcript |
| `awaiting_transcript` | Esperando subtítulos; reintenta con backoff | → `verifying` / `needs_human` |
| `verifying` | Transcript estable, corriendo chequeos | → `resolved` |
| `resolved` | Verificación completa | Estado terminal (pass/fail/review) |
| `needs_human` | Sin transcript utilizable o bloqueo | Revisión manual; terminal |
| `error` | Falla técnica (API, timeout LLM) | Reintento acotado o alerta a ops |

Separar `awaiting_transcript` de `verifying` es lo que evita verificar antes de tiempo. El worker consulta videos con `next_retry_at <= now()` y los reprocesa.

---

## 6. Motor de verificación

Dos tipos de chequeo, deliberadamente separados.

### 6.1 Chequeos determinísticos (R1, R2) — sin LLM

El link y el código son strings conocidos del brief. Match exacto/normalizado: más confiable, instantáneo y gratis.

```python
def check_link_in_description(description: str, expected_link: str) -> RequirementResult:
    normalized = normalize_url(description)  # quita tracking params, lowercase
    met = expected_link.lower() in normalized
    return RequirementResult(met=met, method="deterministic",
                             evidence=expected_link if met else None)
```

Corren *primero*: si fallan, ya hay señal fuerte sin gastar en LLM.

### 6.2 Chequeos con LLM (R3, R4) — sobre el transcript

La LLM recibe (a) el brief y (b) el transcript, y devuelve un veredicto **estructurado** por requisito, con evidencia.

**Nombre del juego mal transcripto:** los subtítulos destrozan nombres (inventados, en inglés/japonés). Se le pasa a la LLM el **nombre canónico del brief** y se le pide detectar si *ese juego* se menciona, tolerando errores fonéticos. Baja mucho los falsos negativos.

**Structured output (esquema de salida):**

```json
{
  "requirements": [
    {
      "requirement_id": "R3",
      "met": true,
      "confidence": 0.95,
      "evidence_quote": "hoy les traigo Mystic Realms, un juego de...",
      "evidence_timestamp_s": 73,
      "reasoning": "menciona el nombre del juego explícitamente"
    }
  ]
}
```

Forzá el JSON con el modo de structured output / tool-use del proveedor. Pedí siempre `evidence_quote` y, si hay timing, `evidence_timestamp_s`: hace que la revisión humana sea de segundos.

### 6.3 Lógica de decisión

```
si algún requisito REQUERIDO determinístico falló  -> FAIL
si todos los automatizables cumplen con confidence >= 0.8
   y hay requisitos visuales pendientes (R5)        -> REVIEW (solo confirmar gameplay)
si todos cumplen y no hay pendientes visuales       -> PASS
si algún requisito LLM tiene confidence < 0.8        -> REVIEW
en cualquier otro caso                               -> FAIL
```

Regla de oro: **ante la duda, REVIEW, nunca PASS automático.** Un falso "cumple" es el peor error porque rompe la confianza del cliente.

---

## 7. Modelo de datos (Supabase / Postgres)

El DDL completo y ejecutable vive en `schema.sql` (correr en el editor SQL de Supabase). Acá va la referencia de diseño: 13 tablas, sus columnas clave y cómo se relacionan.

### Entidades

| Tabla | Propósito | Columnas clave |
|---|---|---|
| `profiles` | Usuarios de la app y su rol; extiende `auth.users` | `id` (=auth.users), `role` (admin/reviewer) |
| `app_settings` | Config clave-valor, incluye el ID del Google Doc a sincronizar | `key`, `value` (jsonb) |
| `channels` | Canales monitoreados (fuente: Google Doc) | `youtube_channel_id` (UC…, único), `resolution_status`, `is_active`, `websub_status`, `websub_lease_expires_at`, `websub_secret` |
| `campaigns` | Campañas de marca (no hard-delete: cerrar con `status`) | `brand`, `name`, `status` |
| `requirements` | Items del brief por campaña (R1..R5) | `campaign_id`, `code`, `type`, `spec` (jsonb), `method`, `required` |
| `campaign_channels` | M:M campaña ↔ canal (qué se espera de quién) | `campaign_id`, `channel_id`, `status`, único `(campaign_id, channel_id)` |
| `video_submissions` | Videos detectados + máquina de estados | `youtube_video_id` (único), `status`, `transcript_attempts`, `next_retry_at`, `error_message`, `resolved_at` |
| `transcripts` | Transcript cacheado, 1:1 con video | `video_id` (único), `source`, `language`, `text`, `segments` (jsonb) |
| `verifications` | Una corrida de verificación por video | `video_id`, `overall_status`, `model`, `raw_output` (jsonb) |
| `requirement_results` | Resultado por requisito dentro de una verificación | `verification_id`, `requirement_id`, `met`, `confidence`, `method`, `evidence`, `evidence_timestamp_s` |
| `reviews` | Decisión humana sobre un video (etiqueta ground-truth para evaluación) | `video_id`, `reviewer_id`, `decision`, `confirmed_gameplay`, `notes` |
| `notifications` | Bitácora de avisos (idempotencia + auditoría) | `video_id`, `channel`, `reason`, `status`, único `(video_id, channel, reason)` |
| `sync_runs` | Historial de sincronizaciones con el Google Doc | `channels_added/removed/unresolved`, `status` |

### Relaciones

- `campaigns` 1—M `requirements` (el brief).
- `campaigns` M—M `channels` vía `campaign_channels`.
- `channels` 1—M `video_submissions`; `campaigns` 1—M `video_submissions` (campaña nullable hasta resolver).
- `video_submissions` 1—1 `transcripts`; 1—M `verifications`; 1—M `reviews`; 1—M `notifications`.
- `verifications` 1—M `requirement_results`; cada resultado referencia un `requirements`.

### Decisiones de diseño clave

- **"Enums" como `text` + `CHECK`** (no ENUM nativo), para poder evolucionar los estados con un simple `ALTER`.
- **Índice del worker** `video_submissions (status, next_retry_at)`: hace eficiente la consulta del backoff ("videos en `awaiting_transcript` con `next_retry_at` vencido").
- **Ciclo de vida del canal:** si un canal sale del Google Doc no se borra (perdería historial), se marca `is_active = false` y se desactiva su WebSub.
- **Integridad:** `CHECK` de que `confidence` ∈ [0,1] y de que un canal `resolved` tenga `youtube_channel_id`. No hard-delete de campañas (preserva el historial de verificaciones).
- **RLS:** usuarios autenticados (UI) leen todo; el backend escribe con `service_role` (bypassea RLS); excepción: la persona puede insertar su propia `review` desde la UI.

**Asociación video → campaña:** del WebSub se obtiene `channelId` → canal. Para la campaña: buscar campañas activas con `campaign_channels` pendiente para ese canal; desambiguar con el link/código presente en la descripción; si hay ambigüedad → `campaign_id` queda null y va a revisión humana.

---

## 8. Interfaz web

Tres vistas mínimas, construidas con Lovable (React + Supabase). La UI **solo lee y muestra**; no calcula la verificación (eso lo hace el backend).

1. **Listado de canales (dashboard):** tarjetas de resumen (total, al día, requieren atención, sin publicar) y una fila por canal con su última publicación y un badge de estado (Cumple / En revisión / No cumple / Pendiente).
2. **Detalle de canal/video:** la checklist de los 5 requisitos con su evidencia (cita + link al timestamp del video) y el veredicto.
3. **Configuración / sincronización:** estado del sync con el Google Doc, fecha de última sincronización, botón de re-sincronizar, y la lista de canales **no resueltos** para confirmar a mano.

---

## 9. División de herramientas: Lovable vs Claude Code

Regla mental: **Lovable construye lo que se ve y se configura; Claude Code construye el motor que corre solo.** Se encuentran en la base de Supabase.

**Lovable** (frontend + datos):
- Las tres vistas de la interfaz web.
- Autenticación / login y roles.
- El esquema de Supabase y sus políticas de seguridad.
- Instrucción crítica al promptearlo: los datos de verificación los produce un servicio externo; la UI solo los lee y muestra (que no invente la lógica de verificación).

**Claude Code** (backend / motor):
- WebSub: suscripción, validación de firma, renovación de leases.
- Worker de transcript con backoff (la librería, los reintentos).
- Motor de verificación: chequeos determinísticos + llamada a la LLM con structured output (incluido el prompt de verificación, que se itera y se mide contra el set dorado).
- Sincronización con Google Docs + resolución nombre→`channel_id`.
- Notificaciones y harness de evaluación.

**Consideración n.º 1:** definir el **esquema de la base de datos primero**, porque es el contrato entre ambas herramientas. Si las tablas no coinciden con lo que el backend escribe, la UI no muestra nada. Orden: esquema → UI sobre el esquema (con datos de prueba) → backend que llena la base → apuntar la UI a datos reales.

**Consideración n.º 2:** conectar Lovable a un proyecto de **Supabase propio** desde el arranque (no a su Cloud gestionado), porque el backend necesita acceso directo a esa misma base con credenciales completas.

---

## 10. Arquitectura de implementación: dos opciones

**Opción A — casi todo en Lovable/Supabase.** Se reformulan los procesos largos como tareas serverless:
- El backoff de transcript no es un worker que "duerme", sino un cron (`pg_cron`) que cada pocos minutos revisa la base por videos pendientes y los procesa.
- Renovación de leases del WebSub y sync del Google Doc → también crons.
- Receptor del webhook y verificación con LLM → edge functions cortas. La llamada a la API de OpenAI desde una edge function es un simple HTTP request con la key como secret.

**El límite de la opción A:** la librería de transcript es de **Python**, y las edge functions corren en **Deno/TypeScript**. En ese entorno las opciones de transcript son peores. Por eso, incluso en un enfoque "mayormente Lovable", lo pragmático suele ser un **pequeño servicio Python solo para obtener el transcript**, que las edge functions invocan.

**Opción B — híbrida.** Lovable para UI + Supabase, más un servicio Python (Claude Code) para el motor (transcript, worker, verificación). Más limpio para las partes Python-pesadas.

**Recomendación:** elegí lo que te lleve más rápido a validar. El componente que define cuánto Python necesitás es el transcript. Como en v1 se usa solo la librería (Python), tener al menos un servicio Python chico para esa pieza es lo más natural.

---

## 11. Costos estimados

> Nota: la facturación de la API de OpenAI es **separada** de la suscripción de ChatGPT (Plus ~US$20/mes). Para un backend automatizado se usa la **API** (pago por token), no la suscripción.

| Ítem | Costo aproximado | Nota |
|---|---|---|
| OpenAI API (verificación) | ~US$0.001–0.015 por video | GPT-4o-mini barato; modelo frontier ~15x más. Con 200 videos/mes: ~US$0.20–3/mes. Es lo MENOS relevante. |
| Lovable | ~US$25/mes (Pro) | Costo de *construcción* (créditos de prompts), no de runtime. |
| Supabase | Free tier o ~US$25/mes (Pro) | Pro incluye ~500k invocaciones de edge function/mes. |
| Servicio Python (si aplica) | ~US$0–7/mes | Gratis en un VPS propio; US$5–7 en Railway/Render. |
| Proxies residenciales | **Diferido** (~US$5–15/mes) | Solo cuando haya tracción; no en v1. |

**Conclusión:** el costo no es el factor que decide; todas las variantes quedan por debajo de ~US$30/mes, y gran parte es costo de construir con Lovable. La decisión se toma por encaje técnico, no por plata.

---

## 12. Salidas y revisión humana

- **Dashboard:** estado de cada canal/submission con su checklist y evidencia (reemplaza la planilla manual).
- **Cola de revisión:** solo `review` y `fail`. Para `review` por R5, muestra "todo el texto cumple, confirmá el gameplay" con link directo al video. La decisión de la persona se guarda en `reviews` (y es la etiqueta ground-truth para evaluación).
- **Notificaciones:** alerta por WhatsApp/email **solo** ante `fail` o `review`. Los `pass` no molestan a nadie. Si no llega nada, está todo bien: eso elimina el trabajo de fin de semana. Cada aviso se registra en `notifications`, con un `unique (video_id, channel, reason)` que evita notificar dos veces lo mismo.

---

## 13. Evaluación (no opcional)

1. **Set dorado:** 30–50 videos pasados etiquetados (cumple/no cumple, requisito por requisito).
2. **Métricas:** precisión y recall por requisito. La crítica es la **tasa de falsos PASS** (debe tender a cero).
3. **Calibración:** ajustar umbrales para que lo ambiguo caiga en `review`, no en `pass`.
4. **Monitoreo continuo:** registrar cada veredicto + la decisión humana (tabla `reviews`); ese registro alimenta un set de evaluación que crece solo.

---

## 14. Stack tecnológico

| Capa | Elección | Por qué |
|---|---|---|
| Interfaz web | Lovable (React + Supabase) | Rápido para UI/CRUD/auth; lee la base compartida |
| Backend / motor | Python (FastAPI + workers) vía Claude Code, o edge functions + `pg_cron` | Procesos stateful, transcript en Python, orquestación, tests |
| Entrada | Google Docs/Drive API | Lista de canales como fuente de verdad |
| Detección | YouTube WebSub + Data API v3 | Push en tiempo real, sin polling |
| Transcript | `youtube-transcript-api` (MIT), detrás de interfaz abstracta | v1 sin proxies; cambiar de motor sin reescribir |
| LLM | API OpenAI con structured output | Veredicto JSON auditable; barato a este volumen |
| Persistencia | Supabase (Postgres) | Contrato compartido backend ↔ UI |
| Notificaciones | WhatsApp/email (infra n8n existente) | Reutiliza lo que ya hay |

---

## 15. Plan de implementación por fases

**Fase 1 — Núcleo de verificación.** Input manual (URL de video): ingesta + verificación + persistencia. Validar la parte difícil (transcript + LLM + decisión) contra el set dorado. Acá se prueba `youtube-transcript-api` sin proxies.

**Fase 2 — Entrada por Google Docs.** Lectura del doc, resolución nombre→`channel_id`, sincronización, manejo de no resueltos.

**Fase 3 — Detección automática (WebSub).** Suscripción por canal, validación de `hub.challenge` y firma, dedup por `videoId`, renovación de leases, worker de transcript con backoff.

**Fase 4 — Interfaz web (Lovable).** Las tres vistas sobre el esquema de Supabase, con auth.

**Fase 5 — Salida, notificaciones y evaluación.** Cola de revisión, alertas, harness de evaluación, monitoreo de falsos PASS.

**Fase 6 (cuando haya mercado) — Robustez y escala.** Proxies residenciales o API de transcript de terceros; opcionalmente visión para R5.

---

## 16. Riesgos técnicos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Bloqueo de IP cloud al usar la librería (RequestBlocked/IpBlocked) | v1 acepta el riesgo; fallback a revisión humana; proxies/API de terceros cuando haya tracción |
| Transcript inexistente o en borrador | Backoff con reintentos; `needs_human` al agotar 24 h |
| ToS de YouTube (descarga de audio para Whisper) | No se usa en v1; sólo se evalúa como fallback futuro |
| Nombre de juego mal transcripto | Nombre canónico al LLM, match fonético tolerante |
| Falsos PASS (el peor error) | Umbral conservador → ante duda, REVIEW; medir esta tasa |
| WebSub duplicados/updates | Idempotencia por `videoId` |
| Suscripción WebSub expira | Job de renovación de leases |
| Canal no resuelto desde el Google Doc | Estado `unresolved` + confirmación manual en la UI |
| Ambigüedad de campaña por video | Desambiguar con link/código; si no, revisión humana |

---

## 17. Flujo end-to-end (resumen)

1. El equipo mantiene la lista de canales en un Google Doc; el sincronizador resuelve cada canal y lo suscribe al WebSub.
2. El influencer sube un video → YouTube notifica vía WebSub.
3. El callback valida la firma, deduplica por `videoId`, crea un `video_submission` en `detected` y responde rápido al hub.
4. Se resuelve influencer → campaña y se trae la metadata (Data API). Los chequeos determinísticos (R1, R2) ya corren con la descripción.
5. Para R3/R4 se necesita el transcript, que puede no estar listo: el video pasa a `awaiting_transcript` y se reintenta con backoff hasta obtenerlo estable o agotar 24 h (`needs_human`).
6. Con transcript estable (`verifying`), se lo une en texto y se lo pasa a la LLM con el brief; structured output devuelve el veredicto por requisito.
7. La lógica de decisión arma `overall_status`, el video pasa a `resolved` y se persiste todo con evidencia.
8. Si es `pass`, queda registrado en silencio. Si es `fail`/`review`, dispara notificación y aparece en la cola y en el dashboard.
9. La persona revisa solo lo ambiguo (incluido confirmar gameplay, R5); su decisión se guarda y alimenta el set de evaluación.

---

> **Nota de implementación:** varios detalles de las APIs de YouTube (WebSub, captions, quota) y el comportamiento de bloqueo de IP de la librería de transcript pueden cambiar. Confirmá contra las fuentes oficiales/repos al momento de construir, y tratá la obtención del transcript como el componente de mayor riesgo a validar temprano.
