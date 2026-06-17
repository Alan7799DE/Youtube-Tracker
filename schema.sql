-- ============================================================================
-- Verificador de publicidad en YouTube — Esquema de base de datos (v4)
-- Target: Supabase (PostgreSQL)
--
-- Cambios clave respecto de v3:
--   - MULTI-TENANT: cada fila pertenece a una organización (org_id). Al registrarse
--     un usuario se crea automáticamente su organización personal. Las RLS aíslan:
--     cada usuario solo ve/escribe lo de sus organizaciones.
--   - Entrada sin Google APIs: canales y brief entran como archivos subidos. Se quitó
--     app_settings (google_doc) y sync_runs pasó a import_runs.
--   - Un video puede servir a varias campañas: el veredicto vive en verifications
--     (con campaign_id); video_submissions ya no tiene campaign_id.
--   - campaign_channels.status: pending | verified | incomplete | failed.
--
-- Convenciones:
--   - IDs uuid con gen_random_uuid()
--   - timestamps timestamptz
--   - "enums" como text + CHECK (más fáciles de evolucionar que los ENUM nativos)
--   - org_id desnormalizado en todas las tablas de negocio → RLS simple y rápida.
--   - RLS: la UI lee/escribe lo de su org (anon key); el backend escribe con la
--     service_role key (bypassea RLS), seteando siempre el org_id correcto.
--
-- Nota de borrado: NO hard-delete de campañas/canales (usar status / is_active),
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
-- 0. PROFILES — datos del usuario (ligado a Supabase Auth)
--    El rol ya NO vive acá: es por organización (ver organization_members).
-- ============================================================================
create table profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table profiles is 'Datos del usuario. Extiende auth.users de Supabase.';

create trigger profiles_set_updated_at before update on profiles
  for each row execute function set_updated_at();

-- ============================================================================
-- 1. ORGANIZATIONS — unidad de aislamiento multi-tenant
-- ============================================================================
create table organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table organizations is 'Organización: unidad de aislamiento. Cada usuario tiene al menos su org personal.';

create trigger organizations_set_updated_at before update on organizations
  for each row execute function set_updated_at();

-- ============================================================================
-- 2. ORGANIZATION_MEMBERS — pertenencia usuario <-> org, con rol
-- ============================================================================
create table organization_members (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations (id) on delete cascade,
  user_id     uuid not null references auth.users (id)    on delete cascade,
  role        text not null default 'admin' check (role in ('admin','reviewer')),
  created_at  timestamptz not null default now(),
  unique (org_id, user_id)
);
comment on table organization_members is 'Quién pertenece a qué organización y con qué rol.';

create index organization_members_user_idx on organization_members (user_id);
create index organization_members_org_idx  on organization_members (org_id);

-- ----------------------------------------------------------------------------
-- Helper: orgs del usuario actual. SECURITY DEFINER para leer membership sin
-- gatillar RLS (evita recursión en las políticas que la usan).
-- ----------------------------------------------------------------------------
create or replace function auth_org_ids()
returns setof uuid
language sql
security definer
set search_path = public
stable
as $$
  select org_id from organization_members where user_id = auth.uid()
$$;

-- ----------------------------------------------------------------------------
-- Alta de usuario: crea profile + organización personal + membership admin.
-- ----------------------------------------------------------------------------
create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_org_id uuid;
  display    text := coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1));
begin
  insert into public.profiles (id, full_name) values (new.id, display);
  insert into public.organizations (name) values (display || ' (personal)')
    returning id into new_org_id;
  insert into public.organization_members (org_id, user_id, role)
    values (new_org_id, new.id, 'admin');
  return new;
end; $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- ============================================================================
-- 3. CHANNELS — canales monitoreados (importados a la grilla editable)
-- ============================================================================
create table channels (
  id                       uuid primary key default gen_random_uuid(),
  org_id                   uuid not null references organizations (id) on delete cascade,
  source_url               text not null,                  -- URL/handle crudo como vino en el import o se cargó a mano
  handle                   text,                           -- @handle, si está disponible
  name                     text,
  youtube_channel_id       text,                           -- UC...; null hasta resolver
  resolution_status        text not null default 'unresolved'
                             check (resolution_status in ('resolved','unresolved','ambiguous')),
  is_active                boolean not null default true,  -- false si salió del último import (no se borra)
  last_imported_at         timestamptz,                    -- última vez visto en un import
  -- estado de la suscripción WebSub (lo usa el job de renovación de leases)
  websub_status            text not null default 'inactive'
                             check (websub_status in ('inactive','pending','active','expired')),
  websub_lease_expires_at  timestamptz,
  websub_secret            text,                           -- para validar el HMAC de los avisos
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  -- integridad: si está resuelto, tiene que tener channel_id
  constraint channels_resolved_has_id
    check (resolution_status <> 'resolved' or youtube_channel_id is not null),
  -- el mismo canal real puede estar en varias orgs, pero único dentro de una org
  unique (org_id, youtube_channel_id)
);
comment on table channels is 'Canales de YouTube monitoreados, importados a la grilla editable de la app.';

create index channels_org_idx               on channels (org_id);
create index channels_resolution_status_idx on channels (resolution_status);
create index channels_websub_lease_idx      on channels (websub_lease_expires_at)
  where websub_status = 'active';  -- el job de renovación sólo mira los activos

create trigger channels_set_updated_at before update on channels
  for each row execute function set_updated_at();

-- ============================================================================
-- 4. CAMPAIGNS — campañas de marca; definen el plazo (starts_at/ends_at)
-- ============================================================================
create table campaigns (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations (id) on delete cascade,
  brand       text not null,
  name        text not null,
  status      text not null default 'active' check (status in ('active','closed')),
  starts_at   date,                                        -- inicio de la ventana (null = desde la creación)
  ends_at     date not null,                               -- fin del plazo (OBLIGATORIO): el "revisor de plazos" mira esto
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint campaigns_window_order check (starts_at is null or starts_at <= ends_at)
);
comment on table campaigns is 'Campañas publicitarias. Cada una define un brief (requirements) y un plazo. No hard-delete.';

create index campaigns_org_idx on campaigns (org_id);

create trigger campaigns_set_updated_at before update on campaigns
  for each row execute function set_updated_at();

-- ============================================================================
-- 5. REQUIREMENTS — requisitos del brief, por campaña (R1..R5)
-- ============================================================================
create table requirements (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations (id) on delete cascade,
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

create index requirements_org_idx         on requirements (org_id);
create index requirements_campaign_id_idx on requirements (campaign_id);

-- ============================================================================
-- 6. CAMPAIGN_CHANNELS — M:M campaña <-> canal; veredicto del influencer
-- ============================================================================
create table campaign_channels (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations (id) on delete cascade,
  campaign_id uuid not null references campaigns (id) on delete cascade,
  channel_id  uuid not null references channels (id)  on delete cascade,
  -- pending: esperando publi | verified: cumplió todo | incomplete: subió pero le falta algo
  -- | failed: venció el plazo sin subir
  status      text not null default 'pending'
                check (status in ('pending','verified','incomplete','failed')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (campaign_id, channel_id)
);
comment on table campaign_channels is 'Asignación campaña<->canal y veredicto del influencer dentro del plazo.';

create index campaign_channels_org_idx      on campaign_channels (org_id);
create index campaign_channels_channel_idx  on campaign_channels (channel_id);
create index campaign_channels_campaign_idx on campaign_channels (campaign_id);

create trigger campaign_channels_set_updated_at before update on campaign_channels
  for each row execute function set_updated_at();

-- ============================================================================
-- 7. VIDEO_SUBMISSIONS — videos que SON la publi + ciclo de procesamiento
--    (los videos que no son la publi se ignoran sin guardar)
-- ============================================================================
create table video_submissions (
  id                   uuid primary key default gen_random_uuid(),
  org_id               uuid not null references organizations (id) on delete cascade,
  channel_id           uuid not null references channels (id)      on delete cascade,
  youtube_video_id     text not null,                      -- dedup por (org_id, youtube_video_id)
  url                  text,
  title                text,
  description          text,
  published_at         timestamptz,
  detected_at          timestamptz not null default now(),
  -- ciclo de procesamiento (NO el veredicto: ese vive en verifications, por campaña)
  status               text not null default 'detected' check (status in (
                         'detected','awaiting_transcript','verifying',
                         'resolved','needs_human','error')),
  transcript_attempts  int not null default 0,
  next_retry_at        timestamptz,                        -- cuándo reintentar el transcript
  error_message        text,                               -- detalle si status = 'error'
  resolved_at          timestamptz,                        -- cuándo llegó a estado terminal
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (org_id, youtube_video_id)
);
comment on table video_submissions is 'Videos detectados que son la publi de >=1 campaña. status = ciclo de procesamiento.';

-- el worker de transcript consulta videos pendientes con next_retry_at vencido
create index video_submissions_worker_idx  on video_submissions (status, next_retry_at);
create index video_submissions_org_idx     on video_submissions (org_id);
create index video_submissions_channel_idx on video_submissions (channel_id);

create trigger video_submissions_set_updated_at before update on video_submissions
  for each row execute function set_updated_at();

-- ============================================================================
-- 8. TRANSCRIPTS — transcript cacheado (1:1 con video)
-- ============================================================================
create table transcripts (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations (id) on delete cascade,
  video_id    uuid not null unique references video_submissions (id) on delete cascade,
  source      text not null check (source in (
                'youtube_auto','youtube_manual','whisper','thirdparty')),
  language    text,
  text        text,                                        -- texto plano unido (join de segmentos)
  segments    jsonb,                                       -- [{text,start,duration}] para timestamps
  fetched_at  timestamptz not null default now()
);
comment on table transcripts is 'Transcript obtenido, cacheado para no re-descargar. 1:1 con el video.';

create index transcripts_org_idx on transcripts (org_id);

-- ============================================================================
-- 9. VERIFICATIONS — una verificación POR VIDEO y POR CAMPAÑA
--    (un mismo video puede cumplir varias campañas)
-- ============================================================================
create table verifications (
  id             uuid primary key default gen_random_uuid(),
  org_id         uuid not null references organizations (id) on delete cascade,
  video_id       uuid not null references video_submissions (id) on delete cascade,
  campaign_id    uuid not null references campaigns (id) on delete cascade,
  overall_status text not null check (overall_status in ('pass','fail','review')),
  model          text,                                     -- ej: 'gpt-4o-mini'
  raw_output     jsonb,                                    -- salida cruda del LLM, para auditoría
  created_at     timestamptz not null default now(),
  unique (video_id, campaign_id)                           -- una verificación por (video, campaña)
);
comment on table verifications is 'Resultado de verificar un video contra una campaña. pass->verified, fail->incomplete, review->cola humana.';

create index verifications_org_idx      on verifications (org_id);
create index verifications_video_idx    on verifications (video_id);
create index verifications_campaign_idx on verifications (campaign_id);

-- ============================================================================
-- 10. REQUIREMENT_RESULTS — resultado por requisito dentro de una verificación
-- ============================================================================
create table requirement_results (
  id                   uuid primary key default gen_random_uuid(),
  org_id               uuid not null references organizations (id) on delete cascade,
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

create index requirement_results_org_idx          on requirement_results (org_id);
create index requirement_results_verification_idx on requirement_results (verification_id);
create index requirement_results_requirement_idx  on requirement_results (requirement_id);

-- ============================================================================
-- 11. REVIEWS — decisión humana (alimenta el set de evaluación)
-- ============================================================================
create table reviews (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references organizations (id) on delete cascade,
  video_id           uuid not null references video_submissions (id) on delete cascade,
  verification_id    uuid references verifications (id) on delete set null,
  reviewer_id        uuid references auth.users (id),
  decision           text not null check (decision in ('pass','fail')),
  confirmed_gameplay boolean,                              -- resultado humano de R5
  notes              text,
  reviewed_at        timestamptz not null default now()
);
comment on table reviews is 'Decisión humana sobre un video. Es la etiqueta ground-truth para evaluación.';

create index reviews_org_idx   on reviews (org_id);
create index reviews_video_idx on reviews (video_id);

-- ============================================================================
-- 12. NOTIFICATIONS — bitácora de avisos (Fase 5; idempotencia + auditoría)
-- ============================================================================
create table notifications (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations (id) on delete cascade,
  video_id    uuid references video_submissions (id) on delete cascade,
  channel     text not null check (channel in ('whatsapp','email')),
  recipient   text,
  reason      text check (reason in ('fail','incomplete','review')),
  status      text not null default 'queued' check (status in ('queued','sent','failed')),
  sent_at     timestamptz,
  created_at  timestamptz not null default now(),
  unique (video_id, channel, reason)  -- no notificar dos veces lo mismo
);
comment on table notifications is 'Avisos (Fase 5). unique evita duplicados.';

create index notifications_org_idx on notifications (org_id);

-- ============================================================================
-- 13. IMPORT_RUNS — historial de importaciones de canales (reemplaza sync_runs)
-- ============================================================================
create table import_runs (
  id                   uuid primary key default gen_random_uuid(),
  org_id               uuid not null references organizations (id) on delete cascade,
  started_at           timestamptz not null default now(),
  finished_at          timestamptz,
  channels_added       int not null default 0,
  channels_removed     int not null default 0,
  channels_unresolved  int not null default 0,
  status               text not null default 'ok' check (status in ('ok','error')),
  notes                text
);
comment on table import_runs is 'Historial de imports de canales (archivo subido o edición de la grilla).';

create index import_runs_org_idx on import_runs (org_id);

-- ============================================================================
-- RLS — Row Level Security (multi-tenant)
--   Cada usuario ve/escribe solo lo de sus organizaciones (auth_org_ids()).
--   El backend usa la service_role key y bypassea RLS.
--   - Config (channels, campaigns, requirements, campaign_channels): CRUD desde la UI.
--   - Resultados (video_submissions, transcripts, verifications, requirement_results,
--     notifications, import_runs): la UI solo LEE; el backend escribe con service_role.
--   - reviews: la UI puede insertar las propias y leer las de su org.
-- ============================================================================
alter table profiles             enable row level security;
alter table organizations        enable row level security;
alter table organization_members enable row level security;
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
alter table import_runs          enable row level security;

-- ---- profiles: cada uno ve/edita el suyo ----------------------------------
create policy "own profile select" on profiles for select to authenticated using (id = auth.uid());
create policy "own profile update" on profiles for update to authenticated using (id = auth.uid());

-- ---- organizations / members: lo de mis orgs ------------------------------
create policy "org select"     on organizations        for select to authenticated using (id in (select auth_org_ids()));
create policy "org update"     on organizations        for update to authenticated using (id in (select auth_org_ids()));
create policy "members select" on organization_members for select to authenticated using (org_id in (select auth_org_ids()));

-- ---- channels (sin hard-delete: se desactivan con is_active) ---------------
create policy "channels select" on channels for select to authenticated using (org_id in (select auth_org_ids()));
create policy "channels insert" on channels for insert to authenticated with check (org_id in (select auth_org_ids()));
create policy "channels update" on channels for update to authenticated using (org_id in (select auth_org_ids())) with check (org_id in (select auth_org_ids()));

-- ---- campaigns (sin hard-delete: se cierran con status='closed') -----------
create policy "campaigns select" on campaigns for select to authenticated using (org_id in (select auth_org_ids()));
create policy "campaigns insert" on campaigns for insert to authenticated with check (org_id in (select auth_org_ids()));
create policy "campaigns update" on campaigns for update to authenticated using (org_id in (select auth_org_ids())) with check (org_id in (select auth_org_ids()));

-- ---- requirements (CRUD desde la UI) --------------------------------------
create policy "requirements select" on requirements for select to authenticated using (org_id in (select auth_org_ids()));
create policy "requirements insert" on requirements for insert to authenticated with check (org_id in (select auth_org_ids()));
create policy "requirements update" on requirements for update to authenticated using (org_id in (select auth_org_ids())) with check (org_id in (select auth_org_ids()));
create policy "requirements delete" on requirements for delete to authenticated using (org_id in (select auth_org_ids()));

-- ---- campaign_channels (CRUD desde la UI) ---------------------------------
create policy "campaign_channels select" on campaign_channels for select to authenticated using (org_id in (select auth_org_ids()));
create policy "campaign_channels insert" on campaign_channels for insert to authenticated with check (org_id in (select auth_org_ids()));
create policy "campaign_channels update" on campaign_channels for update to authenticated using (org_id in (select auth_org_ids())) with check (org_id in (select auth_org_ids()));
create policy "campaign_channels delete" on campaign_channels for delete to authenticated using (org_id in (select auth_org_ids()));

-- ---- resultados: la UI solo LEE (el backend escribe con service_role) ------
create policy "video_submissions select"   on video_submissions   for select to authenticated using (org_id in (select auth_org_ids()));
create policy "transcripts select"         on transcripts         for select to authenticated using (org_id in (select auth_org_ids()));
create policy "verifications select"       on verifications       for select to authenticated using (org_id in (select auth_org_ids()));
create policy "requirement_results select" on requirement_results for select to authenticated using (org_id in (select auth_org_ids()));
create policy "notifications select"       on notifications       for select to authenticated using (org_id in (select auth_org_ids()));
create policy "import_runs select"         on import_runs         for select to authenticated using (org_id in (select auth_org_ids()));

-- ---- reviews: leer las de mi org; insertar las propias --------------------
create policy "reviews select" on reviews for select to authenticated using (org_id in (select auth_org_ids()));
create policy "reviews insert" on reviews for insert to authenticated
  with check (org_id in (select auth_org_ids()) and reviewer_id = auth.uid());
