# Fase 2 — Entrada por archivo + grilla · Plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDO: usá `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkboxes (`- [ ]`) para tracking.

**Goal:** que el sistema sepa qué canales monitorear y contra qué brief, a partir de **archivos subidos** (sin Google APIs): parsear el archivo de canales, resolver cada URL/handle a `channel_id`, reconciliar contra lo existente, y extraer el brief (texto/`.txt`/`.docx`) a una estructura confirmable.

**Architecture:** se agregan módulos al paquete `backend/verifier` de la Fase 1, manteniendo el estilo de dependencias inyectadas y testeo sin red. El parseo de archivos y la reconciliación son funciones puras; la resolución y la extracción del brief aíslan las llamadas externas (YouTube Data API, OpenAI) detrás de parámetros para mockear.

**Tech Stack (suma a Fase 1):** `openpyxl` (xlsx), `python-docx` (docx). Reusa `requests`, `openai`, `pydantic`, `pytest`.

**Alcance (diseño, sección 15 · Fase 2):**
- **Entra:** parseo de archivo de canales (CSV/`.xlsx`), normalización de referencias, resolución URL→`channel_id`, reconciliación (reemplazo con soft-deactivate), parseo de brief (`.txt`/`.docx`/texto) y extracción LLM del brief.
- **No entra:** la **grilla editable y los formularios** son UI → Fase 4. Acá se construye la lógica de backend que esa UI va a invocar. WebSub → Fase 3.

**Prerrequisito:** la Fase 1 está implementada (paquete `backend/verifier`, `models.py`, `checks/`, etc.). Todos los comandos se corren desde `backend/`.

---

## Estructura de archivos (suma a la de Fase 1)

```
backend/
  verifier/
    channels/
      __init__.py
      parse_file.py        # CSV/xlsx -> list[str] de referencias crudas
      refs.py              # "https://youtube.com/@x" -> ChannelRef(kind, value)
      resolve.py           # ChannelRef -> ResolvedChannel | None (YouTube Data API)
      reconcile.py         # (refs nuevas, existentes) -> ReconcilePlan (add/keep/deactivate/reactivate)
    brief/
      __init__.py
      parse_file.py        # .txt/.docx -> texto plano
      extract.py           # texto -> Brief (extracción LLM + structured output)
  tests/
    test_channels_parse_file.py
    test_channels_refs.py
    test_channels_resolve.py
    test_channels_reconcile.py
    test_brief_parse_file.py
    test_brief_extract.py
```

---

## Tarea 0: Dependencias

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/verifier/channels/__init__.py`
- Create: `backend/verifier/brief/__init__.py`

- [ ] **Step 1: Agregar deps en `backend/pyproject.toml`**

En la lista `dependencies`, agregar:

```toml
    "openpyxl>=3.1",
    "python-docx>=1.1",
```

- [ ] **Step 2: Crear los `__init__.py` vacíos**

`backend/verifier/channels/__init__.py` y `backend/verifier/brief/__init__.py`, ambos vacíos.

- [ ] **Step 3: Instalar**

Run: `cd backend && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: instala `openpyxl` y `python-docx` sin errores.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/verifier/channels/__init__.py backend/verifier/brief/__init__.py
git commit -m "chore: deps y paquetes para entrada por archivo (Fase 2)"
```

---

## Tarea 1: Parseo del archivo de canales (CSV / xlsx)

**Files:**
- Create: `backend/verifier/channels/parse_file.py`
- Test: `backend/tests/test_channels_parse_file.py`

- [ ] **Step 1: Escribir el test que falla**

```python
import io
from openpyxl import Workbook
from verifier.channels.parse_file import parse_channels_file


def test_parse_csv_takes_nonempty_lines():
    content = b"url\nhttps://youtube.com/@a\n\nhttps://youtube.com/@b\n"
    refs = parse_channels_file(content, "canales.csv")
    assert refs == ["https://youtube.com/@a", "https://youtube.com/@b"]


def test_parse_csv_skips_header_like_first_cell():
    content = b"canal\n@a\n@b\n"
    refs = parse_channels_file(content, "x.csv")
    assert refs == ["@a", "@b"]


def test_parse_xlsx_first_column():
    wb = Workbook()
    ws = wb.active
    ws.append(["url"])
    ws.append(["https://youtube.com/@a"])
    ws.append(["https://youtube.com/@b"])
    buf = io.BytesIO()
    wb.save(buf)
    refs = parse_channels_file(buf.getvalue(), "canales.xlsx")
    assert refs == ["https://youtube.com/@a", "https://youtube.com/@b"]


def test_unsupported_extension_raises():
    try:
        parse_channels_file(b"x", "canales.pdf")
        assert False, "debería haber lanzado"
    except ValueError:
        pass
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_channels_parse_file.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/channels/parse_file.py`**

```python
from __future__ import annotations
import csv
import io
from openpyxl import load_workbook

_HEADER_HINTS = {"url", "urls", "canal", "canales", "channel", "channels", "link", "links"}


def _looks_like_header(value: str) -> bool:
    return value.strip().lower() in _HEADER_HINTS


def _clean(values: list[str]) -> list[str]:
    out: list[str] = []
    for i, v in enumerate(values):
        v = (v or "").strip()
        if not v:
            continue
        if i == 0 and _looks_like_header(v):
            continue
        out.append(v)
    return out


def parse_channels_file(content: bytes, filename: str) -> list[str]:
    name = filename.lower()
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        first_col = [row[0] for row in rows if row]
        return _clean(first_col)
    if name.endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        first_col = [
            str(row[0]) for row in ws.iter_rows(values_only=True)
            if row and row[0] is not None
        ]
        return _clean(first_col)
    raise ValueError(f"Formato no soportado: {filename} (usá .csv o .xlsx)")
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_channels_parse_file.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/channels/parse_file.py backend/tests/test_channels_parse_file.py
git commit -m "feat: parseo de archivo de canales (CSV/xlsx)"
```

---

## Tarea 2: Normalización de referencias de canal

Convierte una URL/handle crudo en una referencia tipada para resolver con la API.

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
    # URLs
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
    # Bare
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

## Tarea 3: Resolución de canal (YouTube Data API)

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

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/channels/resolve.py backend/tests/test_channels_resolve.py
git commit -m "feat: resolución de canal por handle/id/username"
```

---

## Tarea 4: Reconciliación del import

Función pura: dada la lista nueva de referencias y los canales existentes, calcula qué agregar, mantener, desactivar y reactivar. El match es por URL cruda normalizada (antes de resolver). No toca la base — solo arma el plan.

**Files:**
- Create: `backend/verifier/channels/reconcile.py`
- Test: `backend/tests/test_channels_reconcile.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.channels.reconcile import reconcile, ExistingChannel


def test_reconcile_adds_keeps_deactivates_reactivates():
    new_refs = [
        "https://youtube.com/@a",   # ya existe activo -> keep
        "https://youtube.com/@c",   # no existe -> add
        "https://youtube.com/@d",   # existe inactivo -> reactivate
    ]
    existing = [
        ExistingChannel(id="1", source_url="https://youtube.com/@a", is_active=True),
        ExistingChannel(id="2", source_url="https://youtube.com/@b", is_active=True),   # ya no viene -> deactivate
        ExistingChannel(id="4", source_url="https://youtube.com/@d", is_active=False),
    ]
    plan = reconcile(new_refs, existing)
    assert plan.to_add == ["https://youtube.com/@c"]
    assert {c.id for c in plan.to_keep} == {"1"}
    assert {c.id for c in plan.to_deactivate} == {"2"}
    assert {c.id for c in plan.to_reactivate} == {"4"}


def test_reconcile_is_case_and_slash_insensitive():
    new_refs = ["https://YouTube.com/@A/"]
    existing = [ExistingChannel(id="1", source_url="https://youtube.com/@a", is_active=True)]
    plan = reconcile(new_refs, existing)
    assert plan.to_add == []
    assert {c.id for c in plan.to_keep} == {"1"}
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_channels_reconcile.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/channels/reconcile.py`**

```python
from __future__ import annotations
from pydantic import BaseModel


class ExistingChannel(BaseModel):
    id: str
    source_url: str
    is_active: bool


class ReconcilePlan(BaseModel):
    to_add: list[str]
    to_keep: list[ExistingChannel]
    to_deactivate: list[ExistingChannel]
    to_reactivate: list[ExistingChannel]


def _norm(url: str) -> str:
    return url.strip().lower().rstrip("/")


def reconcile(new_refs: list[str], existing: list[ExistingChannel]) -> ReconcilePlan:
    new_norm = {_norm(u) for u in new_refs}
    existing_by_norm = {_norm(c.source_url): c for c in existing}

    to_add = [u for u in new_refs if _norm(u) not in existing_by_norm]
    to_keep, to_deactivate, to_reactivate = [], [], []
    for c in existing:
        in_new = _norm(c.source_url) in new_norm
        if in_new and c.is_active:
            to_keep.append(c)
        elif in_new and not c.is_active:
            to_reactivate.append(c)
        elif not in_new and c.is_active:
            to_deactivate.append(c)
        # not in_new and not is_active -> sin cambios

    # dedup de to_add manteniendo orden
    seen, deduped = set(), []
    for u in to_add:
        if _norm(u) not in seen:
            seen.add(_norm(u))
            deduped.append(u)
    return ReconcilePlan(to_add=deduped, to_keep=to_keep, to_deactivate=to_deactivate, to_reactivate=to_reactivate)
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_channels_reconcile.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/channels/reconcile.py backend/tests/test_channels_reconcile.py
git commit -m "feat: reconciliación del import de canales (función pura)"
```

> Nota: aplicar el `ReconcilePlan` contra Supabase (insertar nuevos, `is_active=true/false`, resolver + suscribir WebSub) es trabajo de integración que se conecta en la Fase 3 (suscripción) y la Fase 4 (UI). Acá se deja la lógica pura y testeada.

---

## Tarea 5: Parseo del brief (.txt / .docx)

**Files:**
- Create: `backend/verifier/brief/parse_file.py`
- Test: `backend/tests/test_brief_parse_file.py`

- [ ] **Step 1: Escribir el test que falla**

```python
import io
from docx import Document
from verifier.brief.parse_file import parse_brief_file


def test_parse_txt():
    content = "Promociona Mystic Realms con el link https://dl.game/x".encode("utf-8")
    assert "Mystic Realms" in parse_brief_file(content, "brief.txt")


def test_parse_docx():
    doc = Document()
    doc.add_paragraph("Campaña Mystic Realms")
    doc.add_paragraph("Código: GAMER20")
    buf = io.BytesIO()
    doc.save(buf)
    text = parse_brief_file(buf.getvalue(), "brief.docx")
    assert "Mystic Realms" in text
    assert "GAMER20" in text


def test_unsupported_raises():
    try:
        parse_brief_file(b"x", "brief.pdf")
        assert False
    except ValueError:
        pass
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_brief_parse_file.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/brief/parse_file.py`**

```python
from __future__ import annotations
import io
from docx import Document


def parse_brief_file(content: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".txt"):
        return content.decode("utf-8-sig").strip()
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    raise ValueError(f"Formato de brief no soportado: {filename} (usá .txt o .docx)")
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_brief_parse_file.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/brief/parse_file.py backend/tests/test_brief_parse_file.py
git commit -m "feat: parseo de brief (.txt/.docx)"
```

---

## Tarea 6: Extracción del brief con LLM

Convierte el texto libre del brief en un `Brief` estructurado (game_name + requisitos con type/spec/method/required). Es lo que la UI mostrará pre-cargado para que el usuario confirme.

**Files:**
- Create: `backend/verifier/brief/extract.py`
- Test: `backend/tests/test_brief_extract.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.brief.extract import extract_brief, BriefDraft, DraftRequirement


def test_extract_maps_to_brief(mocker):
    draft = BriefDraft(
        game_name="Mystic Realms",
        requirements=[
            DraftRequirement(code="R1", type="link_in_desc", spec={"expected_link": "https://dl.game/x"}, method="deterministic", required=True),
            DraftRequirement(code="R3", type="mention_name", spec={"game_name": "Mystic Realms"}, method="llm", required=True),
        ],
    )
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=draft))]
    client = mocker.Mock()
    client.beta.chat.completions.parse.return_value = completion

    brief = extract_brief("Promociona Mystic Realms, link https://dl.game/x", client=client, model="gpt-4o-mini")

    assert brief.game_name == "Mystic Realms"
    assert {r.code for r in brief.requirements} == {"R1", "R3"}
    r1 = next(r for r in brief.requirements if r.code == "R1")
    assert r1.spec["expected_link"] == "https://dl.game/x"
    assert r1.method == "deterministic"
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_brief_extract.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/brief/extract.py`**

```python
from __future__ import annotations
from pydantic import BaseModel
from verifier.models import Brief, Requirement, RequirementType, Method


class DraftRequirement(BaseModel):
    code: str
    type: RequirementType
    spec: dict = {}
    method: Method
    required: bool = True


class BriefDraft(BaseModel):
    game_name: str
    requirements: list[DraftRequirement]


SYSTEM_PROMPT = (
    "Extraé de un brief publicitario los datos estructurados para verificar un video. "
    "Devolvé el nombre canónico del juego y la lista de requisitos que el brief pide. "
    "Tipos válidos: link_in_desc (con spec.expected_link), code_in_desc (spec.code), "
    "mention_name (spec.game_name), describe_game, show_gameplay. "
    "Asigná method: deterministic para link/código, llm para mención/descripción, human para gameplay. "
    "Incluí SOLO los requisitos que el brief menciona; no inventes."
)


def extract_brief(text: str, *, client, model: str = "gpt-4o-mini") -> Brief:
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format=BriefDraft,
    )
    draft: BriefDraft = completion.choices[0].message.parsed
    return Brief(
        game_name=draft.game_name,
        requirements=[
            Requirement(code=r.code, type=r.type, spec=r.spec, method=r.method, required=r.required)
            for r in draft.requirements
        ],
    )
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_brief_extract.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Correr toda la suite**

Run: `pytest -q`
Expected: PASS (Fase 1 + Fase 2).

- [ ] **Step 6: Commit**

```bash
git add backend/verifier/brief/extract.py backend/tests/test_brief_extract.py
git commit -m "feat: extracción del brief con LLM (structured output)"
```

---

## Validación de la fase (criterios de salida)

- [ ] `pytest -q` pasa completo desde `backend/`.
- [ ] Subiendo un CSV/`.xlsx` real, `parse_channels_file` + `parse_channel_ref` + `resolve_channel` resuelven los canales esperados (probar con una API key real, manual).
- [ ] `reconcile` produce el plan correcto contra un set existente simulado.
- [ ] Subiendo un brief real (`.txt`/`.docx`), `extract_brief` devuelve un `Brief` razonable para confirmar.

## Notas / riesgos a confirmar al implementar

- **Quota:** `channels.list` (forHandle/forUsername/id) cuesta 1 unidad; está bien. Evitar `search` (100 unidades).
- **Handles vs custom URLs:** `forHandle` requiere el `@`. Las `/c/` y `/user/` legacy se resuelven con `forUsername`, que a veces no matchea; en ese caso el canal queda `unresolved` para corregir a mano en la grilla (Fase 4).
- **Aplicar el `ReconcilePlan`** contra Supabase + disparar resolución/suscripción es trabajo de integración (Fases 3–4); acá queda la lógica pura testeada.
- **`docx`/`openpyxl`:** confirmar versiones contra `pyproject.toml`.
