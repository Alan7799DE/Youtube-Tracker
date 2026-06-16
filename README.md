# Verificador de publicidad en YouTube

Sistema que automatiza la verificación de acuerdos publicitarios con influencers de YouTube. Toma una lista de canales desde un Google Doc, detecta automáticamente cuándo esos creadores suben videos, y verifica si cumplen los requisitos publicitarios acordados con la marca.

Reemplaza la revisión manual perfil por perfil (incluso fines de semana) por un monitoreo automático con una interfaz web donde se ve el estado de cada canal.

> ⚠️ **Estado actual: planificación.** Este repositorio contiene por ahora el diseño técnico y el esquema de base de datos. Todavía no hay código de implementación.

---

## El problema

Hoy la verificación es manual: alguien entra canal por canal a confirmar que cada influencer cumplió lo acordado (mostró el link, el código promocional, mencionó el juego, etc.). Es lento, repetitivo y no descansa los fines de semana.

## La solución

Un pipeline automático que:

1. **Entrada** — lee la lista de canales a monitorear desde un Google Doc (fuente de verdad).
2. **Detección** — se entera al instante de cada nuevo video vía WebSub (push de YouTube, sin polling).
3. **Verificación** — obtiene metadata y transcript y compara contra el brief de la campaña, produciendo un veredicto estructurado y auditable.
4. **Presentación** — una interfaz web que muestra el estado de cada canal y deriva a una persona solo los casos ambiguos.

## Qué se verifica

| # | Requisito | Dónde vive | Método |
|---|-----------|-----------|--------|
| R1 | Link de descarga en la descripción | Texto | Determinístico |
| R2 | Código promocional en la descripción | Texto | Determinístico |
| R3 | Menciona el nombre del juego | Audio | LLM sobre transcript |
| R4 | Habla de qué trata el juego | Audio | LLM sobre transcript |
| R5 | Muestra gameplay en pantalla | Visual | Humano (v1) |

**Principio de diseño:** R1–R4 cubren ~90% del valor sin tocar un solo frame de video. R5 es el único que necesita revisión humana en v1.

**Regla de oro:** ante la duda, `REVIEW`, nunca `PASS` automático. Un falso "cumple" es el peor error porque rompe la confianza del cliente.

## Stack tecnológico

| Capa | Elección |
|------|----------|
| Interfaz web | Lovable (React + Supabase) — solo lee y muestra |
| Backend / motor | Python (FastAPI + workers) vía Claude Code |
| Entrada | Google Docs/Drive API |
| Detección | YouTube WebSub + Data API v3 |
| Transcript | `youtube-transcript-api` (MIT), detrás de interfaz abstracta |
| LLM | API OpenAI con structured output |
| Persistencia | Supabase (PostgreSQL) — contrato compartido backend ↔ UI |
| Notificaciones | WhatsApp / email |

## Arquitectura en una línea

**Lovable construye lo que se ve y se configura; el backend (Python) construye el motor que corre solo.** Se encuentran en la base de datos de Supabase, que actúa como contrato compartido entre ambos.

## Plan de implementación por fases

1. **Núcleo de verificación** — input manual (URL de video): ingesta + verificación + persistencia. Validar lo difícil (transcript + LLM + decisión) contra un set dorado.
2. **Entrada por Google Docs** — lectura del doc, resolución nombre→`channel_id`, sincronización.
3. **Detección automática (WebSub)** — suscripción por canal, dedup, renovación de leases, worker de transcript con backoff.
4. **Interfaz web (Lovable)** — las tres vistas sobre el esquema de Supabase, con auth.
5. **Salida, notificaciones y evaluación** — cola de revisión, alertas, harness de evaluación.
6. **Robustez y escala** (cuando haya mercado) — proxies residenciales o API de transcript de terceros; opcionalmente visión para R5.

## Contenido del repositorio

| Archivo | Descripción |
|---------|-------------|
| [`diseno_tecnico_verificador_youtube.md`](diseno_tecnico_verificador_youtube.md) | Documento de diseño técnico completo (arquitectura, flujos, decisiones, riesgos). |
| [`schema.sql`](schema.sql) | Esquema de base de datos ejecutable para Supabase/PostgreSQL (13 tablas + RLS + triggers). |
