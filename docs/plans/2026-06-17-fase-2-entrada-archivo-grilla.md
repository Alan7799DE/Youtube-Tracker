# Fase 2 — Resolución de canales (backend) · Plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDO: usá `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkboxes (`- [ ]`) para tracking.

**Goal:** convertir una referencia de canal (URL/handle, tal como la cargó el usuario en la grilla) en su `channel_id` (`UC…`) usando la YouTube Data API. Es **la única pieza de la entrada que necesita el backend** (porque usa la YouTube API key); la invoca el cron tick de la Fase 3 sobre los canales `unresolved`.

**Architecture:** se agregan dos módulos al paquete `backend/verifier`: `channels/refs.py` (normaliza una referencia cruda a un tipo) y `channels/resolve.py` (resuelve la referencia contra la API). Funciones puras / con HTTP inyectable, testeables sin red.

**Tech Stack:** reusa `requests`, `pydantic`, `pytest` de la Fase 1. **No suma dependencias.**

**Qué cambió respecto del enfoque anterior (importante):**
- El **parseo del archivo de canales** (CSV/`.xlsx`) y la **reconciliación** del import ahora viven en el **frontend** (Fase 4): el usuario sube el archivo, el cliente lo parsea, reconcilia contra la grilla y escribe las filas en `channels` por **RLS** (estado `unresolved`). No pasan por el backend.
- El **brief** se carga con un **formulario manual** (Fase 4), sin archivo ni extracción LLM. Por eso este plan **ya no incluye** parseo de archivos ni extracción de brief.
- El backend solo **resuelve** los canales que la UI dejó en `unresolved` (vía el cron tick).

**Prerrequisito:** la Fase 1 está implementada (paquete `backend/verifier`). Comandos desde `backend/`.

---

## Estructura de archivos (suma a la de Fase 1)

```
backend/
  verifier/
    channels/
      __init__.py
      refs.py              # "https://youtube.com/@x" -> ChannelRef(kind, value)
      resolve.py           # ChannelRef -> ResolvedChannel | None (YouTube Data API)
  tests/
    test_channels_refs.py
    test_channels_resolve.py
```

---

## Tarea 0: Paquete `channels`

**Files:**
- Create: `backend/verifier/channels/__init__.py` (vacío)

- [ ] **Step 1: Crear el `__init__.py` vacío** en `backend/verifier/channels/`.

- [ ] **Step 2: Commit**

```bash
git add backend/verifier/channels/__init__.py
git commit -m "chore: paquete channels (Fase 2)"
```

---

## Tarea 1: Normalización de referencias de canal

Convierte una URL/handle crudo (lo que el usuario cargó en la grilla) en una referencia tipada para resolver con la API.

**Files:**
- Create: `backend/verifier/channels/refs.py`
- Test: `backend/tests/test_channels_refs.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.channels.refs import parse_channel_ref, ChannelRef


def test_channel_id_url():
    r = parse_channel_ref("https://www.youtube.com/channel/UC123abc")
    assert r == ChannelRef(kind="channel_id", value="UC123abc")


def test_handle_url():
    r = parse_channel_ref("https://youtube.com/@GamerPro")
    assert r == ChannelRef(kind="handle", value="GamerPro")


def test_bare_handle():
    assert parse_channel_ref("@GamerPro") == ChannelRef(kind="handle", value="GamerPro")


def test_bare_channel_id():
    assert parse_channel_ref("UC123abc") == ChannelRef(kind="channel_id", value="UC123abc")


def test_legacy_user_url():
    assert parse_channel_ref("https://youtube.com/user/OldName") == ChannelRef(kind="username", value="OldName")


def test_unknown_is_unknown():
    assert parse_channel_ref("Gamer Pro").kind == "unknown"
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_channels_refs.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/channels/refs.py`**

```python
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel

RefKind = Literal["channel_id", "handle", "username", "unknown"]


class ChannelRef(BaseModel):
    kind: RefKind
    value: str


def parse_channel_ref(raw: str) -> ChannelRef:
    s = raw.strip()
    m = re.search(r"youtube\.com/channel/(UC[\w-]+)", s)
    if m:
        return ChannelRef(kind="channel_id", value=m.group(1))
    m = re.search(r"youtube\.com/@([\w.\-]+)", s)
    if m:
        return ChannelRef(kind="handle", value=m.group(1))
    m = re.search(r"youtube\.com/user/([\w.\-]+)", s)
    if m:
        return ChannelRef(kind="username", value=m.group(1))
    m = re.search(r"youtube\.com/c/([\w.\-]+)", s)
    if m:
        return ChannelRef(kind="username", value=m.group(1))
    if s.startswith("@"):
        return ChannelRef(kind="handle", value=s[1:])
    if re.fullmatch(r"UC[\w-]+", s):
        return ChannelRef(kind="channel_id", value=s)
    return ChannelRef(kind="unknown", value=s)
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_channels_refs.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/channels/refs.py backend/tests/test_channels_refs.py
git commit -m "feat: normalización de referencias de canal"
```

---

## Tarea 2: Resolución de canal (YouTube Data API)

**Files:**
- Create: `backend/verifier/channels/resolve.py`
- Test: `backend/tests/test_channels_resolve.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.channels.refs import ChannelRef
from verifier.channels.resolve import resolve_channel, ResolvedChannel


def _resp(mocker, payload):
    resp = mocker.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_resolve_by_handle(mocker):
    payload = {"items": [{"id": "UC999", "snippet": {"title": "GamerPro", "customUrl": "@gamerpro"}}]}
    get = mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="handle", value="gamerpro"), api_key="K")
    assert r == ResolvedChannel(channel_id="UC999", name="GamerPro", handle="@gamerpro")
    assert get.call_args.kwargs["params"]["forHandle"] == "@gamerpro"


def test_resolve_channel_id_passthrough(mocker):
    payload = {"items": [{"id": "UC123", "snippet": {"title": "Canal", "customUrl": "@canal"}}]}
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="channel_id", value="UC123"), api_key="K")
    assert r.channel_id == "UC123"


def test_resolve_not_found_returns_none(mocker):
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, {"items": []}))
    r = resolve_channel(ChannelRef(kind="handle", value="nope"), api_key="K")
    assert r is None


def test_resolve_unknown_kind_returns_none(mocker):
    get = mocker.patch("verifier.channels.resolve.requests.get")
    r = resolve_channel(ChannelRef(kind="unknown", value="Gamer Pro"), api_key="K")
    assert r is None
    get.assert_not_called()
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_channels_resolve.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/channels/resolve.py`**

```python
from __future__ import annotations
from typing import Optional
import requests
from pydantic import BaseModel
from verifier.channels.refs import ChannelRef

API_URL = "https://www.googleapis.com/youtube/v3/channels"


class ResolvedChannel(BaseModel):
    channel_id: str
    name: Optional[str] = None
    handle: Optional[str] = None


def _params_for(ref: ChannelRef, api_key: str) -> Optional[dict]:
    base = {"part": "snippet", "key": api_key}
    if ref.kind == "channel_id":
        return {**base, "id": ref.value}
    if ref.kind == "handle":
        handle = ref.value if ref.value.startswith("@") else f"@{ref.value}"
        return {**base, "forHandle": handle}
    if ref.kind == "username":
        return {**base, "forUsername": ref.value}
    return None  # unknown -> no se resuelve por API


def resolve_channel(ref: ChannelRef, api_key: str) -> Optional[ResolvedChannel]:
    params = _params_for(ref, api_key)
    if params is None:
        return None
    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    item = items[0]
    snippet = item.get("snippet", {})
    return ResolvedChannel(
        channel_id=item["id"],
        name=snippet.get("title"),
        handle=snippet.get("customUrl"),
    )
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_channels_resolve.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Correr toda la suite**

Run: `pytest -q`
Expected: PASS (Fase 1 + Fase 2).

- [ ] **Step 6: Commit**

```bash
git add backend/verifier/channels/resolve.py backend/tests/test_channels_resolve.py
git commit -m "feat: resolución de canal por handle/id/username"
```

---

## Validación de la fase (criterios de salida)

- [ ] `pytest -q` pasa completo desde `backend/`.
- [ ] Con una API key real, `parse_channel_ref` + `resolve_channel` resuelven canales conocidos (probar manual desde un script).

## Notas / riesgos a confirmar al implementar

- **Quota:** `channels.list` (forHandle/forUsername/id) cuesta 1 unidad; está bien. Evitar `search` (100 unidades).
- **Handles vs custom URLs:** `forHandle` requiere el `@`. Las `/c/` y `/user/` legacy se resuelven con `forUsername`, que a veces no matchea; en ese caso el canal queda `unresolved` para corregir a mano en la grilla (Fase 4).
- **Quién llama esto:** el **cron tick** de la Fase 3 levanta los canales `unresolved` de Supabase, llama `resolve_channel`, guarda el `channel_id` (service_role) y suscribe al WebSub. El parseo del archivo y la reconciliación de la grilla son del **frontend** (Fase 4).
