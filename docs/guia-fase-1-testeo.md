# Guía: testear la Fase 1 de punta a punta

La Fase 1 (núcleo de verificación) ya tiene su suite de tests automatizados, pero esos
corren **mockeados** (sin red). Para validarla **de verdad** hace falta correrla contra
videos reales: metadata por la YouTube Data API, transcript por `youtube-transcript-api`
y verificación LLM por OpenAI. Esta guía es el paso a paso completo.

Corre **local**, en tu máquina (IP residencial). No necesita Supabase todavía.

Checklist de lo que aporta el usuario: [`docs/requisitos-externos.md`](requisitos-externos.md) (sección 🟢 Fase 1).

---

## 0. Resumen de lo que vas a hacer

1. Conseguir 2 claves de API (OpenAI + YouTube). *(tu tarea, ~15 min)*
2. Pegarlas en `backend/.env`.
3. Instalar dependencias y correr los tests automatizados (sin claves).
4. Smoke test: verificar **un** video real con la CLI.
5. Armar un set dorado y correr la evaluación completa.

Lo que **pone Claude** (ya está en el repo): todo el código, los `.env.example`, las
plantillas de briefs y del set dorado, y esta guía. Lo que **ponés vos**: las claves y
el etiquetado del set dorado.

---

## 1. Conseguir la API key de OpenAI

Se usa para verificar R3 (menciona el juego) y R4 (describe el juego) sobre el transcript.

1. Entrá a [platform.openai.com](https://platform.openai.com) y logueate.
2. **Activá billing** (es pago por uso, NO es lo mismo que ChatGPT Plus): menú →
   **Settings → Billing → Add payment method**. Cargá un saldo mínimo (p. ej. USD 5).
   Sin billing, las llamadas fallan con error de cuota.
3. Andá a **API keys** (menú izquierdo o [platform.openai.com/api-keys](https://platform.openai.com/api-keys)).
4. **Create new secret key** → copiala YA (no se vuelve a mostrar).
5. Guardala para el paso 3. Empieza con `sk-`.

> Costo: con `gpt-4o-mini` cada video sale fracciones de centavo. 50 videos ≈ centavos.

---

## 2. Conseguir la API key de YouTube Data API v3

Se usa para traer la metadata del video (título, descripción, canal).

1. Entrá a [console.cloud.google.com](https://console.cloud.google.com).
2. Arriba, **selector de proyecto → New Project** (nombre cualquiera, p. ej.
   `yt-verifier`). Esperá a que se cree y seleccionalo.
3. **APIs & Services → Library** → buscá **"YouTube Data API v3"** → **Enable**.
4. **APIs & Services → Credentials → Create Credentials → API key**.
5. Copiá la clave (empieza con `AIza`). Opcional: **Restrict key** → API restrictions →
   limitala a "YouTube Data API v3".

> Cuota: 10.000 unidades/día gratis. Cada metadata cuesta 1 unidad → alcanza de sobra.

---

## 3. Configurar `backend/.env`

```bash
cd backend
cp .env.example .env
```

Editá `backend/.env` y pegá tus claves:

```
OPENAI_API_KEY=sk-...tu-clave...
YOUTUBE_API_KEY=AIza...tu-clave...
LLM_MODEL=gpt-4o-mini
```

`.env` está en `.gitignore`: **nunca se commitea**. Solo se versiona `.env.example`.

---

## 4. Instalar dependencias

```bash
cd backend
python3 -m venv .venv          # si no existe todavía
source .venv/bin/activate
pip install -e ".[dev]"
```

Con `-e .` quedan instalados los comandos `verify-video` y `verify-eval`.

---

## 5. Correr los tests automatizados (no necesita claves)

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```

Deberías ver todos los tests en verde. Esto valida la lógica pura (decisión, checks
determinísticos, parsing) sin tocar la red.

---

## 6. Smoke test: verificar un video real

Probá el pipeline completo contra **un** video. Hay dos briefs de ejemplo en
[`backend/briefs/`](../backend/briefs/):

- `ejemplo-solo-determinista.json` — solo R1/R2: **no necesita OpenAI ni transcript**,
  solo la clave de YouTube. Ideal para el primer smoke test.
- `ejemplo-completo.json` — R1–R4: ejercita también transcript + OpenAI.

```bash
cd backend
source .venv/bin/activate

# Reemplazá VIDEO_ID por el ID real (lo que va después de v= en la URL de YouTube)
python -m verifier.cli VIDEO_ID briefs/ejemplo-solo-determinista.json
# o, con los comandos instalados:
verify-video VIDEO_ID briefs/ejemplo-completo.json
```

Vas a ver el `Verification` en JSON: `overall_status` (`pass`/`fail`/`review`) y el
detalle por requisito. Ajustá `expected_link`/`code` del brief para que matcheen lo que
realmente dice la descripción del video que elijas.

---

## 7. Evaluación completa contra el set dorado

Acá es donde se valida la Fase 1 "completa": muchos videos etiquetados a mano, y una
métrica de cuántos veredictos acierta el sistema.

1. Armá el set dorado siguiendo [`backend/golden/README.md`](../backend/golden/README.md).
   Empezá con 5–10 casos cubriendo `pass`, `fail` y `review`.

   ```bash
   cd backend
   cp golden/example.json golden/golden.json
   # editá golden/golden.json con videos reales y sus etiquetas
   ```

2. Corré el runner:

   ```bash
   verify-eval golden/golden.json
   # o: python -m verifier.eval_cli golden/golden.json
   ```

3. Leé el reporte:

   ```
   OK  abc123: esperado=pass obtenido=pass
   XX  def456: esperado=fail obtenido=review
   ...
   ================================================
     Casos:      10
     Correctos:  9 (90%)
     Falsos PASS:0   <-- debe ser 0
     Errores:    0
   ================================================
   ```

   - **Falsos PASS = 0** es el objetivo principal: nunca decir `pass` cuando no cumple.
   - **Errores** suelen ser videos sin transcript disponible (riesgo conocido de v1):
     el sistema los manda a `review`, no rompe.
   - El comando devuelve código de salida ≠ 0 si hubo falsos PASS o errores (útil en CI).

---

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Faltan variables de entorno` | `.env` sin completar o mal ubicado | Tiene que estar en `backend/.env`; corré los comandos desde `backend/` |
| Error de cuota / 429 en OpenAI | Billing sin activar o sin saldo | Activá billing y cargá saldo (paso 1) |
| `403` / `quotaExceeded` en YouTube | Clave mal restringida o cuota diaria agotada | Revisá la restricción de la clave; esperá al reset diario |
| Muchos `review` por "sin transcript" | El video no tiene subtítulos accesibles | Esperado en v1; elegí videos con subtítulos para validar R3/R4 |
| `command not found: verify-eval` | No corriste `pip install -e ".[dev]"` | Instalá el paquete o usá `python -m verifier.eval_cli` |
