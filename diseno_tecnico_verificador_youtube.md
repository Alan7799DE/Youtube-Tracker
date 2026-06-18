# Documento de diseño técnico — Verificador de publicidad en YouTube (v4)

> Sistema que toma una lista de canales (importada desde un archivo a una grilla editable en la app), detecta automáticamente cuándo esos influencers suben videos, y verifica si cumplen los requisitos publicitarios acordados dentro de un plazo. Reemplaza la revisión manual perfil por perfil (incluso fines de semana) por un monitoreo automático con una interfaz web donde se ve el estado de cada canal. Es multi-usuario: cada usuario ve solo sus propias campañas y canales.

---

## 1. Objetivo y alcance

**Problema:** hoy la verificación es manual, perfil por perfil, incluso fines de semana.

**Objetivo:** que el sistema sepa qué canales monitorear (importados desde un archivo a una grilla editable), detecte las subidas en tiempo real, verifique solo los requisitos automatizables con alta confianza dentro de un plazo acordado, derive a una persona únicamente los casos ambiguos, y muestre todo en una interfaz web multi-usuario.

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
- Brief en PDF (v1 soporta texto pegado, `.txt` y `.docx`; PDF queda para una versión futura).
- Notificaciones (WhatsApp/email) — diferidas a Fase 5.
- Equipos colaborativos: en v1 cada usuario trabaja en su propia organización personal (ver sección 7); invitar a otros miembros queda para más adelante.

---

## 2. Arquitectura general

Cuatro responsabilidades separadas:

1. **Entrada** — saber qué canales monitorear (importados desde un archivo a una grilla editable en la app) y contra qué brief verificar (cargado por archivo o a mano).
2. **Detección** — saber cuándo hay un video nuevo, vía push de YouTube (WebSub).
3. **Ingesta + verificación** — obtener metadata y transcript, y comparar contra el brief produciendo un veredicto estructurado y auditable, por campaña.
4. **Presentación** — una interfaz web multi-usuario que muestra el estado de cada canal y su última publicación.

Las partes pesadas (transcripción, razonamiento del LLM) se delegan a servicios externos vía API. La persistencia y la integración entre componentes viven en Supabase (Postgres), que actúa como contrato compartido entre el backend y la interfaz. **No se usan APIs de Google ni OAuth:** tanto la lista de canales como el brief entran como archivos subidos (snapshots), no como documentos vivos.

---

## 3. Entrada: canales (archivo + grilla) y brief

Hay **dos entradas distintas**, ambas como **archivos subidos** (snapshots), no documentos vivos. No se usan Google APIs ni OAuth.

### 3.1 Canales: subir archivo → grilla editable

El usuario sube un archivo con las URLs de los canales (CSV / `.xlsx`, p. ej. una planilla descargada de Google Sheets). El contenido se carga en una **grilla editable** dentro de la app, donde puede **agregar, eliminar y corregir filas a mano**. La fuente de verdad ya no es un documento externo: **es la propia app** (la grilla).

También se puede pegar/escribir URLs directamente en la grilla, sin archivo.

### 3.2 Resolución de canal (URL → channel_id)

La detección por WebSub necesita el `channel_id` (`UC...`). Como el usuario carga **URLs (o handles)**, la resolución es exacta y barata: `channels.list` con `forHandle` cuesta **1 unidad** de quota (vs `search` por nombre suelto, que cuesta 100). Si una entrada no se puede resolver, queda en estado `unresolved` y aparece marcada en la grilla para corregirla a mano.

### 3.3 Reconciliación al importar / editar

Cada vez que se sube un archivo nuevo, **reemplaza el conjunto activo reconciliando** (nunca borra, para no perder historial):

- Canal del archivo que **ya existía** (match por URL/`channel_id`) → sigue **activo**; no se re-resuelve ni se re-suscribe (no se quema quota ni se resetea el lease de WebSub).
- Canal del archivo que **no existía** → se inserta, resuelve y suscribe al WebSub.
- Canal que estaba activo y **ya no viene** en el archivo → `is_active = false` + desuscribir. Si reaparece en un import futuro → se reactiva.

Las ediciones manuales de la grilla (agregar/eliminar filas) disparan la misma lógica de reconciliación. Cada import queda registrado en `import_runs` (canales agregados/quitados/no resueltos).

### 3.4 Brief: archivo o texto → extracción LLM → confirmación

El brief es **prosa libre** de la que hay que extraer datos estructurados para llenar el `spec` de cada requisito (link esperado, código, nombre del juego) y saber qué requisitos aplican. Formatos soportados en v1: **texto pegado en un textarea, `.txt` y `.docx`** (PDF queda para una versión futura).

El flujo es **extracción con LLM + confirmación humana**:
1. El usuario sube/pega el brief.
2. Una LLM extrae `{link, código, nombre del juego, qué requisitos aplican}`.
3. La app muestra un **formulario pre-cargado y editable** con lo extraído.
4. El usuario **revisa, corrige y confirma** antes de guardar.

El paso de confirmación es **crítico**: el brief define contra qué se verifica; un link mal extraído rompería R1. Por eso la extracción nunca se guarda sin revisión humana. Si no se sube archivo, el formulario arranca vacío y se carga 100% a mano.

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

**Multi-tenant:** si dos organizaciones distintas monitorean el mismo canal, en v1 se suscribe **una vez por fila** (la duplicación es despreciable al volumen esperado). La versión eficiente —una sola suscripción global por canal real con *fan-out* del aviso a todas las orgs que lo siguen— queda como optimización futura.

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

### 5.5 Modelo de dos niveles y máquinas de estados

El veredicto vive en **dos niveles** distintos, deliberadamente separados:

- **Nivel video** = ciclo de procesamiento (¿es la publi?, ¿bajé el transcript?, ¿verifiqué?). El **veredicto** por campaña (`pass`/`fail`/`review`) no es del video sino de cada `verification`.
- **Nivel canal-campaña** = veredicto del influencer ("¿cumplió dentro del plazo?").

**Asociación video → campaña(s).** Al llegar el WebSub se buscan los `campaign_channels` de ese canal que estén `pending` y con la ventana de campaña abierta (entre `starts_at` —o la creación, si es null— y `ends_at`; un video subido antes de que abra la ventana se ignora). Se trae la metadata y se corre el chequeo determinístico R1/R2: por cada campaña candidata cuyo **link o código** aparece en la descripción, el video **es la publi de esa campaña**. **Un mismo video puede servir a varias campañas** (se corre una verificación por cada una; el transcript se baja una sola vez y se reutiliza). Si no matchea ninguna campaña candidata → **no es la publi**, y se **ignora sin guardar** (un influencer sube videos seguido; no se llena la base de ruido).

**Ciclo del video (procesamiento):**

```
detected ──► awaiting_transcript ──► verifying ──► resolved
                  │  ▲                                 (1 verification por campaña matcheada:
                  │  └── reintento (transcript no listo)    pass | fail | review)
                  │
                  └── timeout 24 h ──► needs_human
```

| Estado | Significado | Transición de salida |
|---|---|---|
| `detected` | Es la publi de ≥1 campaña; registrado | Encola primer intento de transcript |
| `awaiting_transcript` | Esperando subtítulos; reintenta con backoff | → `verifying` / `needs_human` |
| `verifying` | Transcript estable, corriendo chequeos (por campaña) | → `resolved` |
| `resolved` | Verificación completa | Terminal; los veredictos están en `verifications` |
| `needs_human` | Sin transcript utilizable o bloqueo | Revisión manual; terminal |
| `error` | Falla técnica (API, timeout LLM) | Reintento acotado o alerta a ops |

**Veredicto del canal-campaña (`campaign_channels.status`):**

| Estado | Significado |
|---|---|
| `pending` | Ventana abierta; todavía no apareció una publi que cumpla. |
| `verified` | Subió la publi y **cumplió todo**. ✅ |
| `incomplete` | Subió la publi pero **le falta algún requisito** (cumplimiento parcial). ⚠️ |
| `failed` | **Venció el plazo y nunca subió** la publi. ❌ |

Mapeo, con precedencia `verified > incomplete > pending` (gana el mejor intento):
- Verificación `pass` → `verified` (deja de esperar).
- Verificación `fail` (es la publi, le falta algo) → `incomplete`. **Modelo indulgente:** mientras la ventana siga abierta, todavía puede pasar a `verified` si re-suben un video corregido.
- Verificación `review` (R5 / baja confianza) → sigue `pending`, va a la cola humana; si confirma → `verified`, si rechaza → `incomplete`.

**Job "revisor de plazos".** Periódicamente busca campañas con `ends_at` vencido y marca como `failed` los `campaign_channel` en `pending` **para los que no existe ninguna verificación** (canal+campaña) — es decir, donde de verdad nunca apareció la publi. **Ojo:** si hay una publi en `review` (esperando confirmación humana), el `campaign_channel` también está en `pending` pero **no** se marca `failed` —sí subió la publi—; queda esperando la decisión humana, que puede resolverse incluso pasado el plazo. Los `incomplete` quedan `incomplete` (subir incompleto ≠ no subir).

Separar `awaiting_transcript` de `verifying` evita verificar antes de tiempo. El worker consulta videos con `next_retry_at <= now()` y los reprocesa.

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

Esta lógica produce el `overall_status` de **cada `verification`** (una por campaña matcheada). Ese veredicto se mapea al estado del `campaign_channel` según la sección 5.5: `pass → verified`, `fail → incomplete`, `review → queda pendiente / cola humana`.

Regla de oro: **ante la duda, REVIEW, nunca PASS automático.** Un falso "cumple" es el peor error porque rompe la confianza del cliente.

---

## 7. Modelo de datos (Supabase / Postgres)

El DDL completo y ejecutable vive en `schema.sql` (correr en el editor SQL de Supabase). Acá va la referencia de diseño: 14 tablas, sus columnas clave y cómo se relacionan. **El sistema es multi-tenant:** cada fila pertenece a una organización (`org_id`), y las RLS garantizan que cada usuario vea solo lo de sus organizaciones.

### Entidades

| Tabla | Propósito | Columnas clave |
|---|---|---|
| `profiles` | Datos del usuario; extiende `auth.users` | `id` (=auth.users), `full_name` |
| `organizations` | Unidad de aislamiento (multi-tenant) | `id`, `name` |
| `organization_members` | Pertenencia usuario ↔ org, con rol | `org_id`, `user_id`, `role` (admin/reviewer), único `(org_id, user_id)` |
| `channels` | Canales monitoreados (importados a la grilla) | `org_id`, `source_url`, `youtube_channel_id`, `resolution_status`, `is_active`, `websub_*`, único `(org_id, youtube_channel_id)` |
| `campaigns` | Campañas de marca; define el plazo (`starts_at`/`ends_at`). No hard-delete | `org_id`, `brand`, `name`, `status`, `starts_at`, `ends_at` |
| `requirements` | Items del brief por campaña (R1..R5) | `org_id`, `campaign_id`, `code`, `type`, `spec` (jsonb), `method`, `required` |
| `campaign_channels` | M:M campaña ↔ canal; veredicto del influencer | `org_id`, `campaign_id`, `channel_id`, `status` (pending/verified/incomplete/failed), único `(campaign_id, channel_id)` |
| `video_submissions` | Videos detectados (que son la publi) + ciclo de procesamiento | `org_id`, `channel_id`, `youtube_video_id` (único), `status`, `transcript_attempts`, `next_retry_at`, `resolved_at` |
| `transcripts` | Transcript cacheado, 1:1 con video | `org_id`, `video_id` (único), `source`, `language`, `text`, `segments` (jsonb) |
| `verifications` | Una verificación **por video y por campaña** | `org_id`, `video_id`, `campaign_id`, `overall_status` (pass/fail/review), `model`, `raw_output` (jsonb) |
| `requirement_results` | Resultado por requisito dentro de una verificación | `org_id`, `verification_id`, `requirement_id`, `met`, `confidence`, `method`, `evidence`, `evidence_timestamp_s` |
| `reviews` | Decisión humana (etiqueta ground-truth para evaluación) | `org_id`, `video_id`, `verification_id`, `reviewer_id`, `decision`, `confirmed_gameplay`, `notes` |
| `notifications` | Bitácora de avisos (Fase 5; idempotencia + auditoría) | `org_id`, `video_id`, `channel`, `reason`, `status`, único `(video_id, channel, reason)` |
| `import_runs` | Historial de importaciones de canales | `org_id`, `channels_added/removed/unresolved`, `status` |

### Relaciones

- `organizations` 1—M `organization_members` (M—M con `auth.users`); 1—M de **todas** las tablas de negocio vía `org_id`.
- `campaigns` 1—M `requirements` (el brief).
- `campaigns` M—M `channels` vía `campaign_channels`.
- `channels` 1—M `video_submissions`.
- `video_submissions` 1—1 `transcripts`; 1—M `verifications` (**una por campaña matcheada**); 1—M `reviews`; 1—M `notifications`.
- `verifications` M—1 `campaigns`; 1—M `requirement_results`; cada resultado referencia un `requirements`.

### Decisiones de diseño clave

- **Multi-tenancy por `org_id`:** se desnormaliza `org_id` en todas las tablas de negocio para que las RLS sean simples y rápidas (`org_id IN (mis orgs)`), sin joins. Al registrarse un usuario se crea automáticamente su **organización personal** (es su único miembro, rol `admin`), así "cada uno ve solo lo suyo" se cumple desde el día uno y queda lista la puerta a equipos a futuro.
- **Un video, varias campañas:** el veredicto vive en `verifications` (con `campaign_id`), no en el video. Por eso el video no tiene `campaign_id`; sus campañas se infieren de sus `verifications`.
- **"Enums" como `text` + `CHECK`** (no ENUM nativo), para evolucionar los estados con un simple `ALTER`.
- **Índice del worker** `video_submissions (status, next_retry_at)`: hace eficiente la consulta del backoff.
- **Ciclo de vida del canal:** un canal que sale del import no se borra (perdería historial); se marca `is_active = false` y se desactiva su WebSub.
- **Unicidad de canal por org:** `unique (org_id, youtube_channel_id)` — dos organizaciones pueden monitorear el mismo canal real.
- **Integridad:** `CHECK` de que `confidence` ∈ [0,1] y de que un canal `resolved` tenga `youtube_channel_id`. **`ends_at` es obligatorio** en `campaigns` (sin plazo no se puede decidir el incumplimiento).
- **Sin hard-delete:** las campañas se cierran (`status='closed'`) y los canales se desactivan (`is_active=false`); la UI no expone borrado de esas entidades (preserva el historial). Los requisitos y asignaciones sí se pueden editar/quitar mientras se arma la campaña, pero un requisito ya usado en una verificación no se puede borrar (la FK lo impide).
- **Resolución event-driven:** al insertarse un canal, un *database webhook* de Supabase avisa al backend, que resuelve el `channel_id` y suscribe al WebSub en lote (sin polling). El cron de renovación de leases reintenta los que quedaron `unresolved` por errores transitorios.
- **Identificación de la publi:** siempre hay un link/código en la descripción (validado con negocio), que asocia el video a la campaña de forma determinística. Los requisitos *a verificar* son los que el usuario elija por campaña (no hace falta que estén los cinco).
- **RLS:** cada usuario lee/escribe solo lo de sus organizaciones. La UI gestiona la **configuración** (canales, campañas, brief, reviews) con la *anon key* gobernada por RLS; el backend escribe los **resultados** (videos, transcripts, verificaciones) con la *service_role key* (bypassea RLS), seteando siempre el `org_id` correcto.

**Asociación video → campaña(s):** del WebSub se obtiene `channelId` → canal (con su `org_id`). Se buscan las campañas de esa org con `campaign_channels` en `pending` y ventana abierta; por cada una cuyo **link o código** aparezca en la descripción se crea una `verification` (un mismo video puede cumplir varias campañas). Si no matchea ninguna, el video se ignora sin guardar.

---

## 8. Interfaz web

Construida con Claude Code (React + Vite + `@supabase/supabase-js`), multi-usuario. La UI **gestiona la configuración** (canales, campañas, brief, revisiones) y **muestra** los resultados; lo que **no** hace es calcular la verificación (eso lo produce el backend). Cada usuario ve solo lo de su organización.

### Navegación

Tras iniciar sesión, una barra lateral con **4 menús principales** + un **menú de cuenta**:

| Menú | Qué hace |
|---|---|
| **Dashboard** | Resumen (total / al día / atención / pendiente) y una fila por canal-campaña con su badge de estado. |
| **Campañas** | Listar/crear/editar campañas, cargar el brief, asignar canales, fijar el plazo. |
| **Canales** | La grilla editable: importar archivo o editar URLs a mano; ver no resueltos. |
| **Revisión** | Cola de videos en `review` (badge con el contador de pendientes). |
| **Cuenta** (abajo) | Perfil, organización, cerrar sesión. |

**Drill-downs** (no son menús; se llega haciendo clic desde otra vista): **detalle de campaña** (desde Campañas) y **detalle de video** (desde Dashboard, campaña o cola).

**Roles:** en v1 cada usuario es `admin` de su org y ve los 4 menús. El rol `reviewer` (equipos a futuro) vería solo Dashboard + Revisión.

### Vistas

1. **Auth + organización personal:** registro/login (Supabase Auth). Al registrarse se crea su organización personal automáticamente.
2. **Dashboard:** tarjetas de resumen y una fila por canal/campaña con su última publicación y un badge de estado (Cumple / Incompleto / En revisión / Pendiente / No cumplió).
3. **Detalle de video:** la checklist de los requisitos con su evidencia (cita + link al timestamp) y el veredicto **por campaña** (un video puede aparecer en varias).
4. **Gestión de campañas:** crear/editar campaña, fijar el plazo (`ends_at` obligatorio), **cargar el brief** (subir `.txt`/`.docx` o pegar texto → extracción LLM → formulario editable → confirmar), **elegir qué requisitos verificar** y **asignar canales** a la campaña.
5. **Importación de canales (grilla):** subir archivo (CSV/`.xlsx`) o editar a mano la grilla de URLs; ver canales **no resueltos** para corregir; historial de imports.
6. **Cola de revisión:** los videos en `review` (confirmar gameplay R5 / baja confianza), con link directo al video; la decisión se guarda en `reviews`.

---

## 9. División de responsabilidades: frontend vs backend

Todo se construye con **Claude Code**. La separación ya no es entre herramientas, sino entre dos responsabilidades que se encuentran en la base de **Supabase**.

Regla mental: **el frontend lee y muestra; el backend escribe.** Supabase es el contrato compartido entre ambos.

**Frontend** (React + Vite + `@supabase/supabase-js`):
- Las vistas de la interfaz web (sección 8).
- Autenticación / login + organización personal, vía **Supabase Auth**.
- **Gestiona la configuración** (canales en la grilla, campañas, brief, asignaciones, reviews) escribiendo con RLS por org.
- **Lee y muestra** los resultados de verificación; no calcula ni inventa la lógica de verificación (eso lo produce el backend).

**Backend / motor** (Python: FastAPI + workers):
- WebSub: suscripción, validación de firma, renovación de leases.
- Worker de transcript con backoff (la librería, los reintentos).
- Motor de verificación: chequeos determinísticos + llamada a la LLM con structured output (incluido el prompt de verificación, que se itera y se mide contra el set dorado), **una verificación por campaña matcheada**.
- Resolución de canal (URL/handle → `channel_id`) y reconciliación del import; job "revisor de plazos".
- Extracción del brief con LLM (devuelve los campos al frontend para que el usuario confirme).
- Harness de evaluación. (Notificaciones → Fase 5.)

**Consideración n.º 1:** definir el **esquema de la base de datos primero**, porque es el contrato entre frontend y backend. Si las tablas no coinciden con lo que el backend escribe, la UI no muestra nada. Orden: esquema → UI sobre el esquema (con datos de prueba) → backend que llena la base → apuntar la UI a datos reales.

**Consideración n.º 2:** crear el proyecto de **Supabase propio** desde el arranque con su `schema.sql` aplicado. El frontend le pega con la *anon key* gobernada por RLS; el backend escribe con la *service_role key* (bypassea RLS). Ambos apuntan a la misma base.

---

## 10. Arquitectura de implementación: dónde corre el backend

El frontend es React (construido con Claude Code), se sirve estáticamente y habla con Supabase. La decisión que queda es **dónde corre el motor del backend**. Dos opciones:

**Opción A — backend mayormente dentro de Supabase.** Se reformulan los procesos largos como tareas serverless de Supabase:
- El backoff de transcript no es un worker que "duerme", sino un cron (`pg_cron`) que cada pocos minutos revisa la base por videos pendientes y los procesa.
- Renovación de leases del WebSub y "revisor de plazos" → también crons.
- Receptor del webhook y verificación con LLM → edge functions cortas (Deno/TS). La llamada a la API de OpenAI desde una edge function es un simple HTTP request con la key como secret.

**El límite de la opción A:** la librería de transcript es de **Python**, y las edge functions corren en **Deno/TypeScript**. En ese entorno las opciones de transcript son peores. Por eso, incluso acá, lo pragmático es un **pequeño servicio Python solo para obtener el transcript**, que las edge functions invocan.

**Opción B — servicio Python dedicado (recomendada).** Un solo servicio Python (FastAPI + workers) corre todo el motor: receptor del WebSub, worker de transcript con backoff, verificación con LLM, resolución/reconciliación del import de canales, extracción del brief y "revisor de plazos". Supabase queda como base de datos + auth, y el frontend React le pega directo para leer.

**Recomendación: opción B.** Como en v1 el transcript se obtiene con la librería de Python, ya necesitás sí o sí un servicio Python. Tener *todo* el motor ahí (en vez de partirlo entre edge functions y un servicio Python) es más simple de razonar, testear y desplegar. Si más adelante conviene mover piezas puntuales a `pg_cron`/edge functions, se puede hacer sin reescribir el resto.

**Despliegue:** el servicio corre en un **VPS de Hostinger**, empaquetado con **Docker** (`docker compose`: la API/WebSub detrás de **Caddy** con HTTPS automático, y los jobs como cron del VPS). La API autenticada y el callback de WebSub se sirven desde **una sola app ASGI** (`verifier/server.py`, que compone los routers). El frontend estático se **sirve desde el mismo VPS con Caddy** (mismo dominio → sin CORS); Vercel/Netlify queda como alternativa opcional. El detalle está en `docs/requisitos-despliegue.md`.

---

## 11. Costos estimados

> Nota: la facturación de la API de OpenAI es **separada** de la suscripción de ChatGPT (Plus ~US$20/mes). Para un backend automatizado se usa la **API** (pago por token), no la suscripción.

| Ítem | Costo aproximado | Nota |
|---|---|---|
| OpenAI API (verificación) | ~US$0.001–0.015 por video | GPT-4o-mini barato; modelo frontier ~15x más. Con 200 videos/mes: ~US$0.20–3/mes. Es lo MENOS relevante. |
| Hosting del frontend | ~US$0 | React estático servido desde el VPS con Caddy (sin costo extra). Vercel/Netlify free tier como opcional. |
| Supabase | Free tier o ~US$25/mes (Pro) | Pro incluye ~500k invocaciones de edge function/mes. |
| Servicio Python (motor) | ~US$0–7/mes | Gratis en un VPS propio; US$5–7 en Railway/Render. |
| Proxies residenciales | **Diferido** (~US$5–15/mes) | Solo cuando haya tracción; no en v1. |

**Conclusión:** el costo no es el factor que decide; todas las variantes quedan por debajo de ~US$30/mes. Construir el frontend con Claude Code (en vez de Lovable) elimina su ~US$25/mes de créditos de construcción. La decisión se toma por encaje técnico, no por plata.

---

## 12. Salidas y revisión humana

- **Dashboard:** estado de cada canal/campaña con su checklist y evidencia (reemplaza la planilla manual). Estados visibles: `verified` / `incomplete` / `review` / `pending` / `failed`.
- **Cola de revisión:** videos en `review`. Para `review` por R5, muestra "todo el texto cumple, confirmá el gameplay" con link directo al video. La decisión de la persona se guarda en `reviews` (y es la etiqueta ground-truth para evaluación).
- **Notificaciones (Fase 5, diferidas):** la idea es alertar por WhatsApp/email **solo** ante `fail`/`incomplete`/`review`, sin molestar con los `pass`, para eliminar el trabajo de fin de semana. La tabla `notifications` ya prevé la idempotencia (`unique (video_id, channel, reason)`), pero el mecanismo de envío no entra en v1.

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
| Interfaz web | React + Vite + `@supabase/supabase-js`, construida con Claude Code | Control total del código, sin herramienta extra ni costo; lee la base compartida |
| Backend / motor | Python (FastAPI + workers) vía Claude Code | Procesos stateful, transcript en Python, orquestación, tests |
| Entrada | Subida de archivos (CSV/`.xlsx` para canales; `.txt`/`.docx`/texto para brief) | Snapshots, sin Google APIs ni OAuth; grilla editable como fuente de verdad |
| Extracción del brief | LLM (structured output) | Texto libre → campos estructurados, con confirmación humana |
| Detección | YouTube WebSub + Data API v3 | Push en tiempo real, sin polling |
| Transcript | `youtube-transcript-api` (MIT), detrás de interfaz abstracta | v1 sin proxies; cambiar de motor sin reescribir |
| LLM | API OpenAI con structured output | Veredicto JSON auditable; barato a este volumen |
| Persistencia | Supabase (Postgres) | Contrato compartido backend ↔ UI |
| Notificaciones | WhatsApp/email (Fase 5; mecanismo a definir) | Diferido; no entra en v1 |

---

## 15. Plan de implementación por fases

**Fase 1 — Núcleo de verificación.** Input manual (URL de video) + brief manual: ingesta + verificación + persistencia. Validar la parte difícil (transcript + LLM + decisión) contra el set dorado. Acá se prueba `youtube-transcript-api` sin proxies.

**Fase 2 — Entrada por archivo + grilla.** Import de canales (CSV/`.xlsx`) a la grilla editable, resolución URL→`channel_id`, reconciliación, manejo de no resueltos. Carga del brief (`.txt`/`.docx`/texto) con extracción LLM + confirmación. Modelo de plazo por campaña.

**Fase 3 — Detección automática (WebSub).** Suscripción por canal, validación de `hub.challenge` y firma, dedup por `videoId`, renovación de leases, worker de transcript con backoff, asociación video→campaña(s) y job "revisor de plazos".

**Fase 4 — Interfaz web + multi-tenancy (Claude Code).** Las vistas en React (sección 8) sobre el esquema de Supabase, con **auth + organización personal** y **RLS por org** (Supabase Auth + skill `frontend-design`).

**Fase 5 — Salida, notificaciones y evaluación.** Cola de revisión, notificaciones (WhatsApp/email), harness de evaluación, monitoreo de falsos PASS.

**Fase 6 (cuando haya mercado) — Robustez y escala.** Proxies residenciales o API de transcript de terceros; brief en PDF (vía LLM multimodal); visión para R5; equipos colaborativos; WebSub con suscripción global + fan-out.

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
| Canal no resuelto desde el import | Estado `unresolved` + corrección manual en la grilla |
| Video que no es la publi marcado como incumplimiento | El `fail` es por **plazo vencido** a nivel campaña, no por video; un video sin link/código se ignora |
| Brief mal extraído por la LLM | Confirmación humana obligatoria del formulario antes de guardar |
| Fuga de datos entre usuarios (multi-tenant) | RLS por `org_id` en todas las tablas; el backend setea `org_id` en cada escritura |

---

## 17. Flujo end-to-end (resumen)

1. El usuario se registra (se crea su organización personal), importa sus canales a la grilla (archivo o a mano) y crea una campaña: sube/pega el brief → la LLM lo extrae → confirma el formulario → asigna canales y fija el plazo. El backend resuelve cada canal y lo suscribe al WebSub.
2. El influencer sube un video → YouTube notifica vía WebSub.
3. El callback valida la firma, deduplica por `videoId` y responde rápido al hub.
4. Se obtiene el canal (y su `org_id`) y la metadata (Data API). Se buscan las campañas de esa org con asignación `pending` y ventana abierta, y se corre R1/R2 sobre la descripción. **Si ninguna matchea → el video se ignora sin guardar.** Si matchea ≥1 campaña → se crea un `video_submission` en `detected`.
5. Para R3/R4 se necesita el transcript, que puede no estar listo: el video pasa a `awaiting_transcript` y se reintenta con backoff hasta obtenerlo estable o agotar 24 h (`needs_human`).
6. Con transcript estable (`verifying`), se lo une en texto y se corre **una verificación por campaña matcheada**; structured output devuelve el veredicto por requisito.
7. La lógica de decisión arma el `overall_status` de cada `verification`, el video pasa a `resolved` y se actualiza el `campaign_channel`: `pass → verified`, `fail → incomplete`, `review → pendiente + cola humana`.
8. Si un `campaign_channel` sigue `pending` cuando vence el plazo **y nunca apareció una publi** (no hay verificación) → el "revisor de plazos" lo marca `failed`. Si hay una publi en `review`, se respeta hasta que el humano decida.
9. La persona revisa solo lo ambiguo (incluido confirmar gameplay, R5); su decisión se guarda y alimenta el set de evaluación. (Las notificaciones de `fail`/`review` quedan para Fase 5.)

---

> **Nota de implementación:** varios detalles de las APIs de YouTube (WebSub, captions, quota) y el comportamiento de bloqueo de IP de la librería de transcript pueden cambiar. Confirmá contra las fuentes oficiales/repos al momento de construir, y tratá la obtención del transcript como el componente de mayor riesgo a validar temprano.
