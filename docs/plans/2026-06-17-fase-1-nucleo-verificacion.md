# Fase 1 — Núcleo de verificación · Plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDO: usá `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkboxes (`- [ ]`) para tracking.

**Goal:** dado un video de YouTube (URL) y un brief cargado a mano, producir un veredicto de cumplimiento publicitario estructurado y auditable (pass/fail/review), validado contra un set dorado.

**Architecture:** un paquete Python puro (`verifier/`) con responsabilidades separadas detrás de interfaces: ingesta de metadata (YouTube Data API), obtención de transcript (detrás de un `TranscriptProvider`), chequeos determinísticos (R1/R2), chequeos LLM (R3/R4 con structured output), lógica de decisión y un orquestador. Las dependencias externas (HTTP, transcript, LLM) se inyectan para poder testear todo con mocks, sin red. Un CLI permite la corrida manual y un harness de evaluación mide contra el set dorado.

**Tech Stack:** Python 3.12, `pydantic` (modelos + structured output), `requests` (YouTube Data API), `youtube-transcript-api` (transcript), `openai` (LLM), `pytest` + `pytest-mock`, `python-dotenv`.

**Alcance (del diseño, sección 15 · Fase 1):**
- **Entra:** input manual de URL + brief → metadata → transcript → R1/R2 determinístico + R3/R4 LLM → decisión → `Verification`. Harness de set dorado.
- **No entra (fases 2–5):** WebSub, entrada por archivos/grilla, UI, multi-tenancy, notificaciones, persistencia en Supabase (la persistencia es la **Tarea 10, opcional**, para validar primero el núcleo sin base).

**Convenciones:**
- TDD estricto: test que falla → mínima implementación → test que pasa → commit.
- Todo el código vive en `backend/`. Los comandos se corren desde `backend/`.
- Sin red en los tests: YouTube/transcript/OpenAI se mockean.

---

## Estructura de archivos

```
backend/
  pyproject.toml                 # deps + config de pytest
  .env.example                   # API keys de ejemplo (no se commitea .env real)
  verifier/
    __init__.py
    models.py                    # pydantic: Brief, Requirement, VideoMetadata, Transcript, RequirementResult, Verification
    metadata.py                  # cliente YouTube Data API (snippet, contentDetails)
    transcript.py                # Protocol TranscriptProvider + impl YouTubeTranscriptProvider
    checks/
      __init__.py
      deterministic.py           # R1 (link) y R2 (código) sobre la descripción
      llm.py                     # R3/R4 sobre el transcript, structured output
    decision.py                  # lógica de decisión → overall_status
    verify.py                    # orquestador verify_video(...)
    cli.py                       # entrada manual
    eval.py                      # harness de set dorado (precisión/recall, falsos PASS)
  golden/
    example.json                 # un caso etiquetado de muestra
  tests/
    test_models.py
    test_deterministic.py
    test_decision.py
    test_transcript.py
    test_metadata.py
    test_llm.py
    test_verify.py
```

Cada archivo tiene una responsabilidad única; las dependencias externas entran por parámetro (inyección), de modo que el orquestador y los chequeos se testean sin tocar la red.

---

## Tarea 0: Scaffolding del proyecto

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/verifier/__init__.py`
- Create: `backend/verifier/checks/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Crear `backend/pyproject.toml`**

```toml
[project]
name = "verifier"
version = "0.1.0"
description = "Núcleo de verificación de publicidad en YouTube (Fase 1)"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "requests>=2.32",
    "youtube-transcript-api>=0.6.2",
    "openai>=1.40",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-mock>=3.14"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Crear `backend/.env.example`**

```bash
OPENAI_API_KEY=sk-...
YOUTUBE_API_KEY=AIza...
LLM_MODEL=gpt-4o-mini
```

- [ ] **Step 3: Crear los `__init__.py` vacíos**

`backend/verifier/__init__.py`, `backend/verifier/checks/__init__.py`, `backend/tests/__init__.py` — los tres como archivos vacíos.

- [ ] **Step 4: Crear el entorno e instalar**

Run: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: instala sin errores; `pytest -q` corre y dice "no tests ran".

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/verifier/__init__.py backend/verifier/checks/__init__.py backend/tests/__init__.py
git commit -m "chore: scaffolding del paquete verifier (Fase 1)"
```

---

## Tarea 1: Modelos de dominio

**Files:**
- Create: `backend/verifier/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import (
    Requirement, Brief, VideoMetadata, TranscriptSegment, Transcript,
    RequirementResult, Verification,
)


def test_transcript_full_text_joins_segments():
    t = Transcript(
        language="es",
        source="youtube_auto",
        segments=[
            TranscriptSegment(text="hola", start=0.0, duration=1.0),
            TranscriptSegment(text="mundo", start=1.0, duration=1.0),
        ],
    )
    assert t.full_text() == "hola mundo"


def test_brief_requirement_lookup_by_type():
    brief = Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R1", type="link_in_desc",
                        spec={"expected_link": "https://dl.game/x"},
                        method="deterministic", required=True),
        ],
    )
    assert brief.requirements[0].spec["expected_link"] == "https://dl.game/x"


def test_verification_holds_results():
    v = Verification(
        overall_status="pass",
        results=[RequirementResult(requirement_code="R1", met=True, method="deterministic")],
    )
    assert v.overall_status == "pass"
    assert v.results[0].met is True
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_models.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'verifier.models'`.

- [ ] **Step 3: Implementar `backend/verifier/models.py`**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

RequirementType = Literal[
    "link_in_desc", "code_in_desc", "mention_name", "describe_game", "show_gameplay"
]
Method = Literal["deterministic", "llm", "human"]
OverallStatus = Literal["pass", "fail", "review"]


class Requirement(BaseModel):
    code: str
    type: RequirementType
    spec: dict = Field(default_factory=dict)
    method: Method
    required: bool = True


class Brief(BaseModel):
    game_name: str
    requirements: list[Requirement]


class VideoMetadata(BaseModel):
    video_id: str
    title: str = ""
    description: str = ""
    channel_id: str = ""
    published_at: Optional[str] = None
    duration: Optional[str] = None


class TranscriptSegment(BaseModel):
    text: str
    start: float
    duration: float


class Transcript(BaseModel):
    language: Optional[str] = None
    source: str = "youtube_auto"
    segments: list[TranscriptSegment]

    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()


class RequirementResult(BaseModel):
    requirement_code: str
    met: bool
    confidence: Optional[float] = None
    method: Optional[Method] = None
    evidence: Optional[str] = None
    evidence_timestamp_s: Optional[int] = None
    reasoning: Optional[str] = None


class Verification(BaseModel):
    overall_status: OverallStatus
    results: list[RequirementResult]
    model: Optional[str] = None
    raw_output: Optional[dict] = None
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/models.py backend/tests/test_models.py
git commit -m "feat: modelos de dominio del verificador"
```

---

## Tarea 2: Chequeos determinísticos (R1 link, R2 código)

**Files:**
- Create: `backend/verifier/checks/deterministic.py`
- Test: `backend/tests/test_deterministic.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc


def test_link_present_is_met():
    r = check_link_in_desc("Bajá el juego: https://DL.Game/x?utm=abc ¡ya!", "https://dl.game/x")
    assert r.met is True
    assert r.method == "deterministic"
    assert r.evidence == "https://dl.game/x"


def test_link_absent_is_not_met():
    r = check_link_in_desc("Mirá mi gameplay", "https://dl.game/x")
    assert r.met is False
    assert r.evidence is None


def test_code_present_case_insensitive():
    r = check_code_in_desc("Usá el código GAMER20 al pagar", "gamer20")
    assert r.met is True
    assert r.evidence == "gamer20"


def test_code_absent():
    r = check_code_in_desc("Sin códigos hoy", "gamer20")
    assert r.met is False
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_deterministic.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/checks/deterministic.py`**

```python
from __future__ import annotations
from verifier.models import RequirementResult


def _normalize(text: str) -> str:
    return text.lower().strip()


def check_link_in_desc(description: str, expected_link: str, code: str = "R1") -> RequirementResult:
    met = _normalize(expected_link) in _normalize(description)
    return RequirementResult(
        requirement_code=code,
        met=met,
        method="deterministic",
        evidence=expected_link if met else None,
    )


def check_code_in_desc(description: str, expected_code: str, code: str = "R2") -> RequirementResult:
    met = _normalize(expected_code) in _normalize(description)
    return RequirementResult(
        requirement_code=code,
        met=met,
        method="deterministic",
        evidence=expected_code if met else None,
    )
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_deterministic.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/checks/deterministic.py backend/tests/test_deterministic.py
git commit -m "feat: chequeos determinísticos R1/R2"
```

---

## Tarea 3: Lógica de decisión

Implementa la sección 6.3 del diseño. Entrada: la lista de `RequirementResult` y los `Requirement` del brief. Salida: `overall_status`.

**Files:**
- Create: `backend/verifier/decision.py`
- Test: `backend/tests/test_decision.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import Requirement, RequirementResult
from verifier.decision import decide

LINK = Requirement(code="R1", type="link_in_desc", spec={}, method="deterministic", required=True)
GAME = Requirement(code="R3", type="mention_name", spec={}, method="llm", required=True)
PLAY = Requirement(code="R5", type="show_gameplay", spec={}, method="human", required=True)


def test_deterministic_required_fail_is_fail():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=False, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm"),
    ]
    assert decide(results, reqs) == "fail"


def test_all_met_no_visual_is_pass():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.9, method="llm"),
    ]
    assert decide(results, reqs) == "pass"


def test_all_met_with_pending_visual_is_review():
    reqs = [LINK, GAME, PLAY]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.9, method="llm"),
    ]
    assert decide(results, reqs) == "review"


def test_low_confidence_llm_is_review():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.6, method="llm"),
    ]
    assert decide(results, reqs) == "review"


def test_llm_required_not_met_high_confidence_is_fail():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=False, confidence=0.95, method="llm"),
    ]
    assert decide(results, reqs) == "fail"


def test_llm_not_met_low_confidence_is_review():
    # Ante la duda, REVIEW: un "no cumple" con baja confianza no debe ser FAIL.
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=False, confidence=0.4, method="llm"),
    ]
    assert decide(results, reqs) == "review"
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_decision.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/decision.py`**

```python
from __future__ import annotations
from verifier.models import Requirement, RequirementResult, OverallStatus

CONFIDENCE_THRESHOLD = 0.8


def decide(results: list[RequirementResult], requirements: list[Requirement]) -> OverallStatus:
    by_code = {r.code: r for r in requirements}
    res_by_code = {r.requirement_code: r for r in results}

    # 1. Si algún requisito determinístico REQUERIDO falló -> FAIL
    for r in results:
        req = by_code.get(r.requirement_code)
        if req and req.required and r.method == "deterministic" and not r.met:
            return "fail"

    # 2. Si algún requisito LLM tiene confidence < umbral -> REVIEW (ante la duda, primero)
    for r in results:
        if r.method == "llm" and (r.confidence is None or r.confidence < CONFIDENCE_THRESHOLD):
            return "review"

    # 3. Si algún requisito LLM REQUERIDO no se cumple con confianza alta -> FAIL
    for r in results:
        req = by_code.get(r.requirement_code)
        if req and req.required and r.method == "llm" and not r.met:
            return "fail"

    # 4. Si hay requisitos visuales/humanos pendientes (sin resultado automático) -> REVIEW
    pending_visual = [
        req for req in requirements
        if req.method == "human" and req.code not in res_by_code
    ]
    if pending_visual:
        return "review"

    # 5. Todo cumple, sin pendientes -> PASS
    return "pass"
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_decision.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/decision.py backend/tests/test_decision.py
git commit -m "feat: lógica de decisión (sección 6.3)"
```

---

## Tarea 4: Transcript provider (interfaz + implementación)

Abstrae la transcripción detrás de un `Protocol` (diseño 5.2) para poder cambiar de motor sin tocar el resto.

**Files:**
- Create: `backend/verifier/transcript.py`
- Test: `backend/tests/test_transcript.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.transcript import YouTubeTranscriptProvider
from verifier.models import Transcript


def test_provider_maps_raw_segments(mocker):
    fake = [
        {"text": "hoy traigo Mystic Realms", "start": 1.2, "duration": 2.0},
        {"text": "un RPG enorme", "start": 3.2, "duration": 1.5},
    ]
    fetch = mocker.patch("verifier.transcript.YouTubeTranscriptApi.get_transcript", return_value=fake)
    provider = YouTubeTranscriptProvider()
    t = provider.get_transcript("vid123")
    assert isinstance(t, Transcript)
    assert t.full_text() == "hoy traigo Mystic Realms un RPG enorme"
    assert t.segments[0].start == 1.2
    fetch.assert_called_once_with("vid123")


def test_provider_returns_none_when_unavailable(mocker):
    mocker.patch(
        "verifier.transcript.YouTubeTranscriptApi.get_transcript",
        side_effect=Exception("TranscriptsDisabled"),
    )
    provider = YouTubeTranscriptProvider()
    assert provider.get_transcript("vid123") is None
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_transcript.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/transcript.py`**

```python
from __future__ import annotations
from typing import Optional, Protocol
from youtube_transcript_api import YouTubeTranscriptApi
from verifier.models import Transcript, TranscriptSegment


class TranscriptProvider(Protocol):
    def get_transcript(self, video_id: str) -> Optional[Transcript]: ...


class YouTubeTranscriptProvider:
    """Implementación con youtube-transcript-api (sin proxies, v1).

    Nota: la API de la librería puede variar entre versiones. Confirmá el método
    correcto (`get_transcript` vs `fetch`) contra la versión instalada.
    """

    def __init__(self, languages: tuple[str, ...] = ("es", "en")):
        self.languages = languages

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=list(self.languages))
        except TypeError:
            raw = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception:
            return None
        segments = [
            TranscriptSegment(text=s["text"], start=float(s["start"]), duration=float(s.get("duration", 0.0)))
            for s in raw
        ]
        return Transcript(language=self.languages[0], source="youtube_auto", segments=segments)
```

> Nota: el primer `except TypeError` cubre versiones de la librería que no aceptan `languages=`. El test mockea `get_transcript`, así que no toca la red.

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_transcript.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/transcript.py backend/tests/test_transcript.py
git commit -m "feat: TranscriptProvider + impl youtube-transcript-api"
```

---

## Tarea 5: Cliente de metadata (YouTube Data API)

**Files:**
- Create: `backend/verifier/metadata.py`
- Test: `backend/tests/test_metadata.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.metadata import fetch_video_metadata
from verifier.models import VideoMetadata


def test_fetch_parses_snippet_and_details(mocker):
    payload = {
        "items": [{
            "snippet": {
                "title": "Jugando Mystic Realms",
                "description": "Link https://dl.game/x código GAMER20",
                "channelId": "UC_abc",
                "publishedAt": "2026-06-01T10:00:00Z",
            },
            "contentDetails": {"duration": "PT12M30S"},
        }]
    }
    resp = mocker.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    mocker.patch("verifier.metadata.requests.get", return_value=resp)

    md = fetch_video_metadata("vid123", api_key="KEY")
    assert isinstance(md, VideoMetadata)
    assert md.title == "Jugando Mystic Realms"
    assert md.channel_id == "UC_abc"
    assert md.duration == "PT12M30S"


def test_fetch_raises_when_no_items(mocker):
    resp = mocker.Mock()
    resp.json.return_value = {"items": []}
    resp.raise_for_status.return_value = None
    mocker.patch("verifier.metadata.requests.get", return_value=resp)
    try:
        fetch_video_metadata("missing", api_key="KEY")
        assert False, "debería haber lanzado"
    except ValueError:
        pass
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_metadata.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/metadata.py`**

```python
from __future__ import annotations
import requests
from verifier.models import VideoMetadata

API_URL = "https://www.googleapis.com/youtube/v3/videos"


def fetch_video_metadata(video_id: str, api_key: str) -> VideoMetadata:
    resp = requests.get(
        API_URL,
        params={"part": "snippet,contentDetails", "id": video_id, "key": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"No se encontró el video {video_id}")
    snippet = items[0].get("snippet", {})
    details = items[0].get("contentDetails", {})
    return VideoMetadata(
        video_id=video_id,
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        channel_id=snippet.get("channelId", ""),
        published_at=snippet.get("publishedAt"),
        duration=details.get("duration"),
    )
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_metadata.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/metadata.py backend/tests/test_metadata.py
git commit -m "feat: cliente de metadata (YouTube Data API)"
```

---

## Tarea 6: Chequeos LLM (R3/R4) con structured output

La LLM recibe el brief (con el `game_name` canónico) y el transcript, y devuelve un veredicto estructurado por requisito. La llamada a OpenAI se aísla detrás de una función con cliente inyectable para testear el parseo sin red.

**Files:**
- Create: `backend/verifier/checks/llm.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import Brief, Requirement, Transcript, TranscriptSegment
from verifier.checks.llm import LLMOutput, LLMRequirementVerdict, check_requirements_llm


def _brief():
    return Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R3", type="mention_name", spec={"game_name": "Mystic Realms"}, method="llm", required=True),
            Requirement(code="R4", type="describe_game", spec={}, method="llm", required=True),
        ],
    )


def _transcript():
    return Transcript(segments=[TranscriptSegment(text="hoy traigo Mystic Realms un RPG", start=70.0, duration=3.0)])


def test_llm_parses_structured_output(mocker):
    parsed = LLMOutput(requirements=[
        LLMRequirementVerdict(requirement_code="R3", met=True, confidence=0.95,
                              evidence_quote="hoy traigo Mystic Realms", evidence_timestamp_s=70,
                              reasoning="menciona el nombre"),
        LLMRequirementVerdict(requirement_code="R4", met=True, confidence=0.88,
                              evidence_quote="un RPG", evidence_timestamp_s=72, reasoning="describe el género"),
    ])
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=parsed))]
    fake_client = mocker.Mock()
    fake_client.beta.chat.completions.parse.return_value = completion

    results = check_requirements_llm(_brief(), _transcript().full_text(), client=fake_client, model="gpt-4o-mini")

    assert {r.requirement_code for r in results} == {"R3", "R4"}
    r3 = next(r for r in results if r.requirement_code == "R3")
    assert r3.met is True and r3.confidence == 0.95
    assert r3.method == "llm"
    assert r3.evidence == "hoy traigo Mystic Realms"
    assert r3.evidence_timestamp_s == 70


def test_llm_only_includes_llm_requirements(mocker):
    parsed = LLMOutput(requirements=[
        LLMRequirementVerdict(requirement_code="R3", met=False, confidence=0.4,
                              evidence_quote=None, evidence_timestamp_s=None, reasoning="no se menciona"),
        LLMRequirementVerdict(requirement_code="R4", met=False, confidence=0.4,
                              evidence_quote=None, evidence_timestamp_s=None, reasoning="no se describe"),
    ])
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=parsed))]
    fake_client = mocker.Mock()
    fake_client.beta.chat.completions.parse.return_value = completion

    results = check_requirements_llm(_brief(), "texto sin nada", client=fake_client, model="gpt-4o-mini")
    assert all(r.method == "llm" for r in results)
    assert all(r.met is False for r in results)
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/checks/llm.py`**

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from verifier.models import Brief, RequirementResult


class LLMRequirementVerdict(BaseModel):
    requirement_code: str
    met: bool
    confidence: float
    evidence_quote: Optional[str] = None
    evidence_timestamp_s: Optional[int] = None
    reasoning: Optional[str] = None


class LLMOutput(BaseModel):
    requirements: list[LLMRequirementVerdict]


SYSTEM_PROMPT = (
    "Sos un verificador de cumplimiento publicitario. Recibís el brief de una campaña "
    "y el transcript de un video. Para cada requisito pedido, decidí si se cumple, con una "
    "confianza de 0 a 1 y una cita textual como evidencia. El nombre del juego puede estar "
    "mal transcripto (errores fonéticos, inglés/japonés): detectá si ESE juego se menciona "
    "tolerando esos errores. Ante la duda, baja la confianza; no inventes evidencia."
)


def _build_user_prompt(brief: Brief, transcript_text: str) -> str:
    llm_reqs = [r for r in brief.requirements if r.method == "llm"]
    lines = [f"Juego (nombre canónico): {brief.game_name}", "", "Requisitos LLM a verificar:"]
    for r in llm_reqs:
        lines.append(f"- {r.code} ({r.type}): {r.spec}")
    lines += ["", "Transcript:", transcript_text]
    return "\n".join(lines)


def check_requirements_llm(
    brief: Brief, transcript_text: str, *, client, model: str = "gpt-4o-mini"
) -> list[RequirementResult]:
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(brief, transcript_text)},
        ],
        response_format=LLMOutput,
    )
    parsed: LLMOutput = completion.choices[0].message.parsed
    return [
        RequirementResult(
            requirement_code=v.requirement_code,
            met=v.met,
            confidence=v.confidence,
            method="llm",
            evidence=v.evidence_quote,
            evidence_timestamp_s=v.evidence_timestamp_s,
            reasoning=v.reasoning,
        )
        for v in parsed.requirements
    ]
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/checks/llm.py backend/tests/test_llm.py
git commit -m "feat: chequeos LLM R3/R4 con structured output"
```

---

## Tarea 7: Orquestador `verify_video`

Ensambla metadata + determinístico + transcript + LLM + decisión. Todas las dependencias externas se inyectan.

**Files:**
- Create: `backend/verifier/verify.py`
- Test: `backend/tests/test_verify.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import Brief, Requirement, VideoMetadata, Transcript, TranscriptSegment, RequirementResult
from verifier.verify import verify_video


def _brief():
    return Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R1", type="link_in_desc", spec={"expected_link": "https://dl.game/x"}, method="deterministic", required=True),
            Requirement(code="R2", type="code_in_desc", spec={"code": "GAMER20"}, method="deterministic", required=True),
            Requirement(code="R3", type="mention_name", spec={"game_name": "Mystic Realms"}, method="llm", required=True),
        ],
    )


def test_full_pass(mocker):
    md = VideoMetadata(video_id="v", title="t", description="https://dl.game/x GAMER20", channel_id="UC")
    transcript = Transcript(segments=[TranscriptSegment(text="traigo Mystic Realms", start=10.0, duration=2.0)])

    metadata_client = mocker.Mock(return_value=md)
    provider = mocker.Mock()
    provider.get_transcript.return_value = transcript
    llm = mocker.Mock(return_value=[
        RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm"),
    ])

    v = verify_video("v", _brief(), metadata_client=metadata_client, transcript_provider=provider, llm_check=llm)
    assert v.overall_status == "pass"
    assert {r.requirement_code for r in v.results} == {"R1", "R2", "R3"}


def test_missing_transcript_goes_to_review(mocker):
    md = VideoMetadata(video_id="v", title="t", description="https://dl.game/x GAMER20", channel_id="UC")
    metadata_client = mocker.Mock(return_value=md)
    provider = mocker.Mock()
    provider.get_transcript.return_value = None
    llm = mocker.Mock()

    v = verify_video("v", _brief(), metadata_client=metadata_client, transcript_provider=provider, llm_check=llm)
    assert v.overall_status == "review"
    llm.assert_not_called()
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_verify.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/verify.py`**

```python
from __future__ import annotations
from typing import Callable, Optional
from verifier.models import Brief, Verification, VideoMetadata, Transcript, RequirementResult
from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc
from verifier.decision import decide

MetadataClient = Callable[[str], VideoMetadata]
LLMCheck = Callable[[Brief, str], list[RequirementResult]]


def _run_deterministic(brief: Brief, description: str) -> list[RequirementResult]:
    out: list[RequirementResult] = []
    for req in brief.requirements:
        if req.type == "link_in_desc":
            out.append(check_link_in_desc(description, req.spec.get("expected_link", ""), code=req.code))
        elif req.type == "code_in_desc":
            out.append(check_code_in_desc(description, req.spec.get("code", ""), code=req.code))
    return out


def evaluate_brief(
    brief: Brief, metadata: VideoMetadata, transcript: Optional[Transcript], *, llm_check: LLMCheck
) -> Verification:
    """Núcleo de verificación SIN fetch: recibe metadata y transcript ya obtenidos.
    Reutilizable para verificar varias campañas con un mismo transcript (Fase 3)."""
    results = _run_deterministic(brief, metadata.description)
    has_llm = any(r.method == "llm" for r in brief.requirements)
    if has_llm:
        if transcript is None:
            # Sin transcript no se pueden correr R3/R4 -> a revisión humana.
            return Verification(overall_status="review", results=results)
        results += llm_check(brief, transcript.full_text())
    status = decide(results, brief.requirements)
    return Verification(overall_status=status, results=results)


def verify_video(
    video_id: str,
    brief: Brief,
    *,
    metadata_client: MetadataClient,
    transcript_provider,
    llm_check: LLMCheck,
) -> Verification:
    metadata = metadata_client(video_id)
    has_llm = any(r.method == "llm" for r in brief.requirements)
    transcript = transcript_provider.get_transcript(video_id) if has_llm else None
    return evaluate_brief(brief, metadata, transcript, llm_check=llm_check)
```

> Nota: `verify_video` hace el fetch y delega en `evaluate_brief`. La Fase 3 reutiliza `evaluate_brief` para verificar **varias campañas con un mismo transcript** (el transcript se baja una sola vez). En el test, `llm_check` se inyecta como `Callable[[Brief, str], list[RequirementResult]]`; en producción se pasa `lambda b, t: check_requirements_llm(b, t, client=openai_client, model=MODEL)` (ver Tarea 8).

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_verify.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/verify.py backend/tests/test_verify.py
git commit -m "feat: orquestador verify_video"
```

---

## Tarea 8: CLI de corrida manual

Permite verificar un video real desde la terminal, leyendo las API keys del entorno y el brief de un archivo JSON.

**Files:**
- Create: `backend/verifier/cli.py`

- [ ] **Step 1: Implementar `backend/verifier/cli.py`**

```python
from __future__ import annotations
import argparse
import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from verifier.models import Brief
from verifier.metadata import fetch_video_metadata
from verifier.transcript import YouTubeTranscriptProvider
from verifier.checks.llm import check_requirements_llm
from verifier.verify import verify_video


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Verificar un video contra un brief (Fase 1)")
    parser.add_argument("video_id", help="ID del video de YouTube")
    parser.add_argument("brief", help="Ruta a un JSON con el brief")
    args = parser.parse_args(argv)

    youtube_key = os.environ["YOUTUBE_API_KEY"]
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    openai_client = OpenAI()  # toma OPENAI_API_KEY del entorno

    brief = Brief.model_validate_json(open(args.brief, encoding="utf-8").read())

    verification = verify_video(
        args.video_id,
        brief,
        metadata_client=lambda vid: fetch_video_metadata(vid, api_key=youtube_key),
        transcript_provider=YouTubeTranscriptProvider(),
        llm_check=lambda b, t: check_requirements_llm(b, t, client=openai_client, model=model),
    )
    print(verification.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verificar que el CLI arranca (sin red)**

Run: `python -m verifier.cli --help`
Expected: imprime el help con `video_id` y `brief`.

- [ ] **Step 3: Commit**

```bash
git add backend/verifier/cli.py
git commit -m "feat: CLI de verificación manual"
```

---

## Tarea 9: Harness de evaluación (set dorado)

Mide el verificador contra un set de videos etiquetados. La métrica crítica es la **tasa de falsos PASS** (debe tender a cero). El cómputo de métricas se testea con un set dorado sintético y un verificador mockeado (sin red).

**Files:**
- Create: `backend/golden/example.json`
- Create: `backend/verifier/eval.py`
- Test: `backend/tests/test_eval.py`

- [ ] **Step 1: Crear `backend/golden/example.json`**

```json
[
  {
    "video_id": "EXAMPLE_VIDEO_ID",
    "expected_overall": "pass",
    "brief": {
      "game_name": "Mystic Realms",
      "requirements": [
        {"code": "R1", "type": "link_in_desc", "spec": {"expected_link": "https://dl.game/x"}, "method": "deterministic", "required": true},
        {"code": "R3", "type": "mention_name", "spec": {"game_name": "Mystic Realms"}, "method": "llm", "required": true}
      ]
    }
  }
]
```

- [ ] **Step 2: Escribir el test que falla**

```python
from verifier.models import Verification, RequirementResult
from verifier.eval import evaluate, GoldenCase, Brief


def test_evaluate_counts_false_pass(mocker):
    cases = [
        GoldenCase(video_id="a", expected_overall="fail",
                   brief=Brief(game_name="G", requirements=[])),
        GoldenCase(video_id="b", expected_overall="pass",
                   brief=Brief(game_name="G", requirements=[])),
    ]

    def fake_runner(video_id, brief):
        if video_id == "a":
            return Verification(overall_status="pass", results=[])  # falso PASS
        return Verification(overall_status="pass", results=[])

    report = evaluate(cases, runner=fake_runner)
    assert report.total == 2
    assert report.false_pass == 1
    assert report.correct == 1
```

- [ ] **Step 3: Correr el test para ver que falla**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 4: Implementar `backend/verifier/eval.py`**

```python
from __future__ import annotations
import json
from typing import Callable
from pydantic import BaseModel
from verifier.models import Brief, Verification, OverallStatus


class GoldenCase(BaseModel):
    video_id: str
    expected_overall: OverallStatus
    brief: Brief


class EvalReport(BaseModel):
    total: int
    correct: int
    false_pass: int  # esperado != pass pero el sistema dijo pass (el peor error)


Runner = Callable[[str, Brief], Verification]


def load_golden(path: str) -> list[GoldenCase]:
    data = json.loads(open(path, encoding="utf-8").read())
    return [GoldenCase.model_validate(c) for c in data]


def evaluate(cases: list[GoldenCase], runner: Runner) -> EvalReport:
    correct = 0
    false_pass = 0
    for case in cases:
        result = runner(case.video_id, case.brief)
        if result.overall_status == case.expected_overall:
            correct += 1
        if result.overall_status == "pass" and case.expected_overall != "pass":
            false_pass += 1
    return EvalReport(total=len(cases), correct=correct, false_pass=false_pass)
```

- [ ] **Step 5: Correr el test para ver que pasa**

Run: `pytest tests/test_eval.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Correr toda la suite**

Run: `pytest -q`
Expected: PASS (todos los tests de las Tareas 1–9).

- [ ] **Step 7: Commit**

```bash
git add backend/golden/example.json backend/verifier/eval.py backend/tests/test_eval.py
git commit -m "feat: harness de evaluación con set dorado"
```

---

## Tarea 10 (opcional): Persistencia en Supabase

Persistir la `Verification` y sus `RequirementResult` en la base (tablas `verifications` y `requirement_results` del `schema.sql`). En Fase 1 el `video_submission` se crea a mano para el video probado. Se aísla detrás de un repositorio mockeable; el test de integración real contra Supabase es **manual**.

**Files:**
- Create: `backend/verifier/repository.py`
- Test: `backend/tests/test_repository.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import Verification, RequirementResult
from verifier.repository import save_verification


def test_save_inserts_verification_and_results(mocker):
    client = mocker.Mock()
    table = mocker.Mock()
    client.table.return_value = table
    table.insert.return_value = table
    table.execute.return_value = mocker.Mock(data=[{"id": "ver-1"}])

    v = Verification(
        overall_status="pass",
        results=[RequirementResult(requirement_code="R1", met=True, method="deterministic")],
        model="gpt-4o-mini",
    )
    ver_id = save_verification(
        client, org_id="org-1", video_id="vid-1", campaign_id="camp-1",
        requirement_ids={"R1": "req-1"}, verification=v,
    )
    assert ver_id == "ver-1"
    assert client.table.call_count >= 2  # verifications + requirement_results
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/repository.py`**

```python
from __future__ import annotations
from verifier.models import Verification


def save_verification(
    client, *, org_id: str, video_id: str, campaign_id: str,
    requirement_ids: dict[str, str], verification: Verification,
) -> str:
    """Inserta la verificación y sus resultados. `client` es un cliente Supabase
    con service_role (bypassea RLS). `requirement_ids` mapea code -> requirements.id."""
    ver_row = (
        client.table("verifications")
        .insert({
            "org_id": org_id,
            "video_id": video_id,
            "campaign_id": campaign_id,
            "overall_status": verification.overall_status,
            "model": verification.model,
            "raw_output": verification.raw_output,
        })
        .execute()
    )
    verification_id = ver_row.data[0]["id"]

    rows = [
        {
            "org_id": org_id,
            "verification_id": verification_id,
            "requirement_id": requirement_ids[r.requirement_code],
            "met": r.met,
            "confidence": r.confidence,
            "method": r.method,
            "evidence": r.evidence,
            "evidence_timestamp_s": r.evidence_timestamp_s,
        }
        for r in verification.results
        if r.requirement_code in requirement_ids
    ]
    if rows:
        client.table("requirement_results").insert(rows).execute()
    return verification_id
```

> Para usarlo de verdad: `pip install supabase`, crear el cliente con `create_client(SUPABASE_URL, SERVICE_ROLE_KEY)`, y haber corrido `schema.sql` en el proyecto. El test mockea el cliente; la verificación contra una base real es un paso manual.

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_repository.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/repository.py backend/tests/test_repository.py
git commit -m "feat: persistencia de verificación en Supabase (opcional)"
```

---

## Validación de la fase (criterios de salida)

- [ ] `pytest -q` pasa completo desde `backend/`.
- [ ] El CLI corre contra un video real con transcript y devuelve un veredicto coherente.
- [ ] El harness de evaluación corre sobre un set dorado de 30–50 casos y reporta **0 (o casi 0) falsos PASS**.
- [ ] Si el transcript no se obtiene, el video cae a `review` (no rompe).

## Notas / riesgos a confirmar al implementar

- **API de `youtube-transcript-api`:** confirmar `get_transcript` vs `fetch` contra la versión instalada (la librería cambió su interfaz entre versiones).
- **Bloqueo de IP del transcript:** correr la validación desde una IP residencial (local). En cloud esperá bloqueos intermitentes (diseño 5.2).
- **`response_format` de OpenAI:** confirmar que el modelo elegido soporta structured output con `beta.chat.completions.parse` y un modelo pydantic; ajustar si la versión del SDK difiere.
- **Set dorado:** hay que armarlo con videos reales etiquetados a mano (30–50). `golden/example.json` es solo la forma del archivo.
