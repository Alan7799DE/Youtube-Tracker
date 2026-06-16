-- ============================================================================
-- Verificador de publicidad en YouTube — Esquema de base de datos (v3)
-- Target: Supabase (PostgreSQL)
--
-- Convenciones:
--   - IDs uuid con gen_random_uuid()
--   - timestamps timestamptz
--   - "enums" como text + CHECK (más fáciles de evolucionar que los ENUM nativos)
--   - RLS habilitado; el backend (servicio) usa la service_role key y bypassea RLS,
--     la UI (Lovable) usa usuarios autenticados gobernados por las políticas de abajo.
--
-- Nota de borrado: NO hacer hard-delete de campañas (usar status='closed'),
--   para preservar la integridad del historial de verificaciones.
-- ============================================================================

create extension if not exists pgcrypto;  -- gen_random_uuid()

-- Trigger reutilizable para mantener updated_at
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end; $$;

-- ============================================================================
-- 0. PROFILES — usuarios de la app y su rol (ligado a Supabase Auth)
-- ============================================================================
create table profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text,
  role        text not null default 'reviewer' check (role in ('admin','reviewer')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table profiles is 'Usuarios de la app y su rol. Extiende auth.users de Supabase.';

create trigger profiles_set_updated_at before update on profiles
  for each row execute function set_updated_at();

-- ============================================================================
-- 0b. APP_SETTINGS — configuración (incluye el ID del Google Doc a sincronizar)
-- ============================================================================
create table app_settings (
  key         text primary key,
  value       jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);
comment on table app_settings is 'Config clave-valor. Ej: google_doc -> {"document_id":"..."}.';

create trigger app_settings_set_updated_at before update on app_settings
  for each row execute function set_updated_at();

-- ============================================================================
-- 1. CHANNELS — canales de YouTube a monitorear (fuente: Google Doc)
-- ============================================================================
create table channels (
  id                       uuid primary key default gen_random_uuid(),
  source_label             text not null,                  -- texto crudo como vino en el Google Doc
  handle                   text,                           -- @handle, si está disponible
  name                     text,
  youtube_channel_id       text unique,                    -- UC...; null hasta resolver
  resolution_status        text not null default 'unresolved'
                             check (resolution_status in ('resolved','unresolved','ambiguous')),
  is_active                boolean not null default true,  -- false si salió del Google Doc (no se borra)
  last_synced_at           timestamptz,                    -- última vez visto en el doc
  -- estado de la suscripción WebSub (lo usa el job de renovación de leases)
  websub_status            text not null default 'inactive'
                             check (websub_status in ('inactive','pending','active','expired')),
  websub_lease_expires_at  timestamptz,
  websub_secret            text,                           -- para validar el HMAC de los avisos
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  -- integridad: si está resuelto, tiene que tener channel_id
  constraint channels_resolved_has_id
    check (resolution_status <> 'resolved' or youtube_channel_id is not null)
);
comment on table channels is 'Canales de YouTube monitoreados, sincronizados desde el Google Doc.';

create index channels_resolution_status_idx on channels (resolution_status);
create index channels_websub_lease_idx       on channels (websub_lease_expires_at)
  where websub_status = 'active';  -- el job de renovación sólo mira los activos
-- (youtube_channel_id ya está indexado por la restricción UNIQUE)

create trigger channels_set_updated_at before update on channels
  for each row execute function set_updated_at();

-- ============================================================================
-- 2. CAMPAIGNS — campañas de marca
-- ============================================================================
create table campaigns (
  id          uuid primary key default gen_random_uuid(),
  brand       text not null,
  name        text not null,
  status      text not null default 'active' check (status in ('active','closed')),
  starts_at   date,
  ends_at     date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table campaigns is 'Campañas publicitarias. Cada una define un brief (requirements). No hard-delete.';

create trigger campaigns_set_updated_at before update on campaigns
  for each row execute function set_updated_at();

-- ============================================================================
-- 3. REQUIREMENTS — requisitos del brief, por campaña (R1..R5)
-- ============================================================================
create table requirements (
  id          uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns (id) on delete cascade,
  code        text not null,                              -- etiqueta humana: 'R1', 'R2', ...
  type        text not null check (type in (
                'link_in_desc','code_in_desc','mention_name','describe_game','show_gameplay')),
  spec        jsonb not null default '{}'::jsonb,         -- {expected_link} | {code} | {game_name}
  method      text not null check (method in ('deterministic','llm','human')),
  required    boolean not null default true,
  created_at  timestamptz not null default now(),
  unique (campaign_id, code)
);
comment on table requirements is 'Items verificables del brief. method define qué chequeador corre.';
comment on column requirements.spec is 'Valor esperado según type, ej: {"expected_link":"https://..."}';

create index requirements_campaign_id_idx on requirements (campaign_id);

-- ============================================================================
-- 4. CAMPAIGN_CHANNELS — relación M:M campaña <-> canal (qué se espera de quién)
-- ============================================================================
create table campaign_channels (
  id          uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns (id) on delete cascade,
  channel_id  uuid not null references channels (id)  on delete cascade,
  status      text not null default 'pending' check (status in ('pending','submitted','verified')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (campaign_id, channel_id)
);
comment on table campaign_channels is 'Asignación: qué canales participan de qué campaña.';

create index campaign_channels_channel_idx  on campaign_channels (channel_id);
create index campaign_channels_campaign_idx on campaign_channels (campaign_id);

create trigger campaign_channels_set_updated_at before update on campaign_channels
  for each row execute function set_updated_at();

-- ============================================================================
-- 5. VIDEO_SUBMISSIONS — videos detectados + máquina de estados
-- ============================================================================
create table video_submissions (
  id                   uuid primary key default gen_random_uuid(),
  channel_id           uuid not null references channels (id)  on delete cascade,
  campaign_id          uuid references campaigns (id) on delete set null,  -- null si aún ambiguo
  youtube_video_id     text not null unique,               -- idempotencia: dedup por acá
  url                  text,
  title                text,
  description          text,
  published_at         timestamptz,
  detected_at          timestamptz not null default now(),
  status               text not null default 'detected' check (status in (
                         'detected','awaiting_transcript','verifying',
                         'resolved','needs_human','error')),
  transcript_attempts  int not null default 0,
  next_retry_at        timestamptz,                        -- cuándo reintentar el transcript
  error_message        text,                               -- detalle si status = 'error'
  resolved_at          timestamptz,                        -- cuándo llegó a estado terminal
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
comment on table video_submissions is 'Videos detectados vía WebSub. status sigue la máquina de estados.';

-- el worker de transcript consulta videos pendientes con next_retry_at vencido
create index video_submissions_worker_idx   on video_submissions (status, next_retry_at);
create index video_submissions_channel_idx  on video_submissions (channel_id);
create index video_submissions_campaign_idx on video_submissions (campaign_id);

create trigger video_submissions_set_updated_at before update on video_submissions
  for each row execute function set_updated_at();

-- ============================================================================
-- 6. TRANSCRIPTS — transcript cacheado (1:1 con video)
-- ============================================================================
create table transcripts (
  id          uuid primary key default gen_random_uuid(),
  video_id    uuid not null unique references video_submissions (id) on delete cascade,
  source      text not null check (source in (
                'youtube_auto','youtube_manual','whisper','thirdparty')),
  language    text,
  text        text,                                        -- texto plano unido (join de segmentos)
  segments    jsonb,                                       -- [{text,start,duration}] para timestamps
  fetched_at  timestamptz not null default now()
);
comment on table transcripts is 'Transcript obtenido, cacheado para no re-descargar. 1:1 con el video.';

-- ============================================================================
-- 7. VERIFICATIONS — una corrida de verificación por video (permite re-correr)
-- ============================================================================
create table verifications (
  id             uuid primary key default gen_random_uuid(),
  video_id       uuid not null references video_submissions (id) on delete cascade,
  overall_status text not null check (overall_status in ('pass','fail','review')),
  model          text,                                     -- ej: 'gpt-4o-mini'
  raw_output     jsonb,                                    -- salida cruda del LLM, para auditoría
  created_at     timestamptz not null default now()
);
comment on table verifications is 'Resultado global de una corrida de verificación de un video.';

create index verifications_video_idx on verifications (video_id);

-- ============================================================================
-- 8. REQUIREMENT_RESULTS — resultado por requisito dentro de una verificación
-- ============================================================================
create table requirement_results (
  id                   uuid primary key default gen_random_uuid(),
  verification_id      uuid not null references verifications (id) on delete cascade,
  requirement_id       uuid not null references requirements (id),  -- RESTRICT: no borrar requisito con historial
  met                  boolean not null,
  confidence           numeric(4,3) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  method               text check (method in ('deterministic','llm','human')),
  evidence             text,                               -- cita / valor encontrado
  evidence_timestamp_s int,                                -- segundo del video (si aplica)
  created_at           timestamptz not null default now()
);
comment on table requirement_results is 'Veredicto por requisito, con evidencia y confianza.';

create index requirement_results_verification_idx on requirement_results (verification_id);
create index requirement_results_requirement_idx  on requirement_results (requirement_id);

-- ============================================================================
-- 9. REVIEWS — decisión humana (alimenta el set de evaluación)
-- ============================================================================
create table reviews (
  id                 uuid primary key default gen_random_uuid(),
  video_id           uuid not null references video_submissions (id) on delete cascade,
  verification_id    uuid references verifications (id) on delete set null,
  reviewer_id        uuid references auth.users (id),
  decision           text not null check (decision in ('pass','fail')),
  confirmed_gameplay boolean,                              -- resultado humano de R5
  notes              text,
  reviewed_at        timestamptz not null default now()
);
comment on table reviews is 'Decisión humana sobre un video. Es la etiqueta ground-truth para evaluación.';

create index reviews_video_idx on reviews (video_id);

-- ============================================================================
-- 10. NOTIFICATIONS — bitácora de avisos (idempotencia + auditoría)
-- ============================================================================
create table notifications (
  id          uuid primary key default gen_random_uuid(),
  video_id    uuid references video_submissions (id) on delete cascade,
  channel     text not null check (channel in ('whatsapp','email')),
  recipient   text,
  reason      text check (reason in ('fail','review')),
  status      text not null default 'queued' check (status in ('queued','sent','failed')),
  sent_at     timestamptz,
  created_at  timestamptz not null default now(),
  unique (video_id, channel, reason)  -- no notificar dos veces lo mismo
);
comment on table notifications is 'Avisos enviados por fail/review. unique evita duplicados.';

-- ============================================================================
-- 11. SYNC_RUNS — bitácora de sincronizaciones con el Google Doc
-- ============================================================================
create table sync_runs (
  id                   uuid primary key default gen_random_uuid(),
  started_at           timestamptz not null default now(),
  finished_at          timestamptz,
  channels_added       int not null default 0,
  channels_removed     int not null default 0,
  channels_unresolved  int not null default 0,
  status               text not null default 'ok' check (status in ('ok','error')),
  notes                text
);
comment on table sync_runs is 'Historial de corridas de sincronización del Google Doc.';

-- ============================================================================
-- RLS — Row Level Security
--   Punto de partida: usuarios autenticados (la UI de Lovable) pueden LEER todo.
--   Las escrituras las hace el backend con la service_role key, que bypassea RLS.
--   Excepción: reviews puede escribir el usuario autenticado (la persona revisa desde la UI).
--   Refinar con roles/permisos cuando haga falta.
-- ============================================================================
alter table profiles             enable row level security;
alter table app_settings         enable row level security;
alter table channels             enable row level security;
alter table campaigns            enable row level security;
alter table requirements         enable row level security;
alter table campaign_channels    enable row level security;
alter table video_submissions    enable row level security;
alter table transcripts          enable row level security;
alter table verifications        enable row level security;
alter table requirement_results  enable row level security;
alter table reviews              enable row level security;
alter table notifications        enable row level security;
alter table sync_runs            enable row level security;

-- Lectura para usuarios autenticados
create policy "auth read profiles"            on profiles            for select to authenticated using (true);
create policy "auth read app_settings"        on app_settings        for select to authenticated using (true);
create policy "auth read channels"            on channels            for select to authenticated using (true);
create policy "auth read campaigns"           on campaigns           for select to authenticated using (true);
create policy "auth read requirements"        on requirements        for select to authenticated using (true);
create policy "auth read campaign_channels"   on campaign_channels   for select to authenticated using (true);
create policy "auth read video_submissions"   on video_submissions   for select to authenticated using (true);
create policy "auth read transcripts"         on transcripts         for select to authenticated using (true);
create policy "auth read verifications"       on verifications       for select to authenticated using (true);
create policy "auth read requirement_results" on requirement_results for select to authenticated using (true);
create policy "auth read reviews"             on reviews             for select to authenticated using (true);
create policy "auth read notifications"       on notifications       for select to authenticated using (true);
create policy "auth read sync_runs"           on sync_runs           for select to authenticated using (true);

-- La persona puede registrar su propia revisión desde la UI
create policy "auth insert own review" on reviews
  for insert to authenticated with check (reviewer_id = auth.uid());
