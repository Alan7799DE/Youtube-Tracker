# Set dorado — Fase 1

Casos reales etiquetados a mano que sirven para **validar el motor de verificación**:
cada caso es un video real + el brief de su campaña + el veredicto correcto según una
persona. El runner (`python -m verifier.eval_cli`) corre el motor sobre cada uno y mide
cuántos veredictos coinciden, contando aparte los **falsos PASS** (el peor error).

> El etiquetado es trabajo del equipo (no técnico). Se puede arrancar con 5–10 casos;
> la meta del plan son 30–50. La plantilla está en [`example.json`](example.json).

## Formato

El archivo es un **array JSON** de casos. Cada caso:

```json
{
  "video_id": "dQw4w9WgXcQ",          // ID del video (lo de después de v= en la URL)
  "expected_overall": "pass",          // veredicto correcto: pass | fail | review
  "brief": { "game_name": "...", "requirements": [ ... ] }
}
```

El `brief` usa el mismo esquema que el resto del sistema. Tipos de requisito (`type`):

| type            | método        | `spec` que espera                 | qué verifica |
|-----------------|---------------|-----------------------------------|--------------|
| `link_in_desc`  | deterministic | `{"expected_link": "https://..."}`| R1 — link en la descripción |
| `code_in_desc`  | deterministic | `{"code": "MICODIGO"}`            | R2 — código promocional |
| `mention_name`  | llm           | `{"game_name": "..."}`           | R3 — menciona el juego |
| `describe_game` | llm           | `{"game_name": "..."}`           | R4 — describe de qué trata |
| `show_gameplay` | human         | `{}`                              | R5 — gameplay (siempre a revisión humana en v1) |

## Cómo elegir `expected_overall`

Es el veredicto que **debería** dar el sistema, según las reglas de decisión:

- **`pass`** — todos los requisitos requeridos cumplen y no queda nada pendiente de humano.
- **`fail`** — algún requisito requerido NO cumple (link/código ausente, no menciona el juego con confianza alta, o un humano marcó que no cumple).
- **`review`** — hay ambigüedad: el LLM quedó por debajo del umbral de confianza, o falta un veredicto humano (p. ej. cualquier brief con `show_gameplay`).

**Regla de oro:** ante la duda, etiquetá `review`, nunca `pass`. Un falso `pass` rompe la
confianza del cliente, y el runner lo cuenta como el error más grave.

## Cómo armar el tuyo

1. Copiá la plantilla: `cp example.json golden.json`.
2. Por cada video, conseguí su `video_id`, definí el `brief` de su campaña y etiquetá el
   `expected_overall` mirando el video a mano.
3. Cubrí los tres veredictos (incluí casos `fail` y `review`, no solo `pass`).
4. Corré: `python -m verifier.eval_cli golden/golden.json`.

Los IDs de la plantilla (`REEMPLAZAR_...`) son placeholders: hay que cambiarlos por
videos reales antes de correr el runner.
