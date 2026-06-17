# Fase 3 — Detección automática (WebSub) · Plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDO: usá `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkboxes (`- [ ]`) para tracking.

**Goal:** enterarse en tiempo real de cada subida vía YouTube WebSub, registrar los videos que son la publi (asociándolos a su(s) campaña(s)), y mantener vivo el sistema con los jobs de backoff de transcript, renovación de leases y "revisor de plazos".

**Architecture:** un servicio FastAPI con un endpoint de callback (GET challenge + POST notificación) y un conjunto de funciones puras para la mecánica (suscripción al hub, parseo del feed Atom, validación HMAC, scheduling de backoff, reconocimiento de incumplimientos). Toda la lógica se aísla en funciones testeables sin red; el endpoint es una capa delgada encima.

**Tech Stack (suma a Fases 1–2):** `fastapi`, `uvicorn[standard]`, `httpx` (TestClient). Reusa `requests`, `pydantic`, `pytest`. La asociación video→campaña reusa los chequeos determinísticos de la Fase 1.

**Alcance (diseño, sección 15 · Fase 3):**
- **Entra:** suscripción/renovación WebSub, validación de `hub.challenge` y firma HMAC, parseo del feed, dedup por `videoId`, asociación video→campaña(s), worker de transcript con backoff, job "revisor de plazos".
- **No entra:** la UI (Fase 4) y las notificaciones (Fase 5). La persistencia real contra Supabase se aísla detrás de repositorios mockeables; los tests no tocan la base.

**Prerrequisito:** Fases 1 y 2 implementadas. Comandos desde `backend/`. El endpoint de callback debe ser accesible públicamente para que el hub lo alcance (en validación local, usar un túnel tipo `ngrok`).

---

## Estructura de archivos (suma a Fases 1–2)

```
backend/
  verifier/
    websub/
      __init__.py
      subscribe.py     # POST al hub (subscribe/unsubscribe)
      feed.py          # parseo del feed Atom -> (video_id, channel_id)
      signature.py     # validación HMAC X-Hub-Signature
      callback.py      # process_notification(...) pura (valida + parsea + callback)
      app.py           # FastAPI: GET challenge + POST notificación
    jobs/
      __init__.py
      backoff.py       # scheduling del transcript (next_retry_at, transiciones)
      leases.py        # renovación de suscripciones por vencer
      deadlines.py     # revisor de plazos (pending sin verificación -> failed)
    association.py     # video -> campaña(s) por link/código en la descripción
    verify_multi.py    # verifica varias campañas reutilizando un transcript (usa evaluate de Fase 1)
    channel_status.py  # mapeo veredicto -> estado del campaign_channel (precedencia)
  tests/
    test_websub_subscribe.py
    test_websub_feed.py
    test_websub_signature.py
    test_websub_callback.py
    test_websub_app.py
    test_jobs_backoff.py
    test_jobs_leases.py
    test_jobs_deadlines.py
    test_association.py
    test_verify_multi.py
    test_channel_status.py
```

---

## Tarea 0: Dependencias y paquetes

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/verifier/websub/__init__.py`
- Create: `backend/verifier/jobs/__init__.py`

- [ ] **Step 1: Agregar deps en `backend/pyproject.toml`**

En `dependencies`:

```toml
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
```

En `optional-dependencies.dev`:

```toml
    "httpx>=0.27",
```

- [ ] **Step 2: Crear `__init__.py` vacíos**

`backend/verifier/websub/__init__.py` y `backend/verifier/jobs/__init__.py`.

- [ ] **Step 3: Instalar**

Run: `cd backend && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: instala FastAPI/uvicorn/httpx sin errores.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/verifier/websub/__init__.py backend/verifier/jobs/__init__.py
git commit -m "chore: deps FastAPI y paquetes para WebSub (Fase 3)"
```

---

## Tarea 1: Suscripción al hub (PubSubHubbub)

**Files:**
- Create: `backend/verifier/websub/subscribe.py`
- Test: `backend/tests/test_websub_subscribe.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.websub.subscribe import topic_url, send_subscription


def test_topic_url():
    assert topic_url("UC123") == "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC123"


def test_send_subscribe_posts_expected_form(mocker):
    resp = mocker.Mock(status_code=202)
    post = mocker.patch("verifier.websub.subscribe.requests.post", return_value=resp)
    ok = send_subscription(
        channel_id="UC123",
        callback_url="https://app.example.com/websub/callback",
        secret="s3cr3t",
        mode="subscribe",
    )
    assert ok is True
    data = post.call_args.kwargs["data"]
    assert data["hub.mode"] == "subscribe"
    assert data["hub.topic"] == "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC123"
    assert data["hub.callback"] == "https://app.example.com/websub/callback"
    assert data["hub.secret"] == "s3cr3t"


def test_send_subscription_returns_false_on_error(mocker):
    resp = mocker.Mock(status_code=500)
    mocker.patch("verifier.websub.subscribe.requests.post", return_value=resp)
    ok = send_subscription(channel_id="UC1", callback_url="https://x/cb", secret="s", mode="unsubscribe")
    assert ok is False
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_websub_subscribe.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/websub/subscribe.py`**

```python
from __future__ import annotations
from typing import Literal
import requests

HUB_URL = "https://pubsubhubbub.appspot.com/subscribe"
TOPIC_TEMPLATE = "https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"


def topic_url(channel_id: str) -> str:
    return TOPIC_TEMPLATE.format(channel_id=channel_id)


def send_subscription(
    *, channel_id: str, callback_url: str, secret: str,
    mode: Literal["subscribe", "unsubscribe"],
) -> bool:
    data = {
        "hub.mode": mode,
        "hub.topic": topic_url(channel_id),
        "hub.callback": callback_url,
        "hub.secret": secret,
        "hub.verify": "async",
    }
    resp = requests.post(HUB_URL, data=data, timeout=15)
    return resp.status_code in (202, 204)
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_websub_subscribe.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/websub/subscribe.py backend/tests/test_websub_subscribe.py
git commit -m "feat: suscripción WebSub al hub"
```

---

## Tarea 2: Parseo del feed Atom

**Files:**
- Create: `backend/verifier/websub/feed.py`
- Test: `backend/tests/test_websub_feed.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.websub.feed import parse_notification, VideoEvent

FEED = b"""<?xml version="1.0"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>VID123</yt:videoId>
    <yt:channelId>UC456</yt:channelId>
    <title>Mi video</title>
  </entry>
</feed>"""


def test_parse_extracts_ids():
    ev = parse_notification(FEED)
    assert ev == VideoEvent(video_id="VID123", channel_id="UC456", title="Mi video")


def test_parse_returns_none_without_entry():
    body = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert parse_notification(body) is None
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_websub_feed.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/websub/feed.py`**

```python
from __future__ import annotations
from typing import Optional
import xml.etree.ElementTree as ET
from pydantic import BaseModel

NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


class VideoEvent(BaseModel):
    video_id: str
    channel_id: str
    title: Optional[str] = None


def parse_notification(body: bytes) -> Optional[VideoEvent]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    entry = root.find("atom:entry", NS)
    if entry is None:
        return None
    vid = entry.findtext("yt:videoId", namespaces=NS)
    chan = entry.findtext("yt:channelId", namespaces=NS)
    title = entry.findtext("atom:title", namespaces=NS)
    if not vid or not chan:
        return None
    return VideoEvent(video_id=vid, channel_id=chan, title=title)
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_websub_feed.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/websub/feed.py backend/tests/test_websub_feed.py
git commit -m "feat: parseo del feed Atom de WebSub"
```

---

## Tarea 3: Validación de firma HMAC

**Files:**
- Create: `backend/verifier/websub/signature.py`
- Test: `backend/tests/test_websub_signature.py`

- [ ] **Step 1: Escribir el test que falla**

```python
import hashlib
import hmac
from verifier.websub.signature import is_valid_signature


def test_valid_signature():
    body = b"<feed/>"
    secret = "s3cr3t"
    digest = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    assert is_valid_signature(body, f"sha1={digest}", secret) is True


def test_invalid_signature():
    assert is_valid_signature(b"<feed/>", "sha1=deadbeef", "s3cr3t") is False


def test_missing_header():
    assert is_valid_signature(b"<feed/>", None, "s3cr3t") is False
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_websub_signature.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/websub/signature.py`**

```python
from __future__ import annotations
import hashlib
import hmac
from typing import Optional


def is_valid_signature(body: bytes, header: Optional[str], secret: str) -> bool:
    if not header or "=" not in header:
        return False
    algo, _, received = header.partition("=")
    algos = {"sha1": hashlib.sha1, "sha256": hashlib.sha256}
    if algo not in algos:
        return False
    expected = hmac.new(secret.encode(), body, algos[algo]).hexdigest()
    return hmac.compare_digest(expected, received)
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_websub_signature.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/websub/signature.py backend/tests/test_websub_signature.py
git commit -m "feat: validación de firma HMAC de WebSub"
```

---

## Tarea 4: Procesamiento de la notificación (lógica pura)

Orquesta: valida firma → parsea feed → busca el secreto del canal → invoca un callback con el `VideoEvent`. Todo inyectado para testear sin red.

**Files:**
- Create: `backend/verifier/websub/callback.py`
- Test: `backend/tests/test_websub_callback.py`

- [ ] **Step 1: Escribir el test que falla**

```python
import hashlib
import hmac
from verifier.websub.callback import process_notification

FEED = b"""<?xml version="1.0"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry><yt:videoId>VID1</yt:videoId><yt:channelId>UC1</yt:channelId><title>t</title></entry>
</feed>"""


def _sig(body, secret):
    return "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()


def test_valid_notification_invokes_callback():
    seen = []
    ok = process_notification(
        FEED, _sig(FEED, "s1"),
        get_channel_secret=lambda chan: "s1" if chan == "UC1" else None,
        on_video=lambda ev: seen.append((ev.channel_id, ev.video_id)),
    )
    assert ok is True
    assert seen == [("UC1", "VID1")]


def test_bad_signature_is_rejected():
    seen = []
    ok = process_notification(
        FEED, "sha1=bad",
        get_channel_secret=lambda chan: "s1",
        on_video=lambda ev: seen.append(ev),
    )
    assert ok is False
    assert seen == []


def test_unknown_channel_is_ignored():
    ok = process_notification(
        FEED, _sig(FEED, "s1"),
        get_channel_secret=lambda chan: None,
        on_video=lambda ev: None,
    )
    assert ok is False
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_websub_callback.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/websub/callback.py`**

```python
from __future__ import annotations
from typing import Callable, Optional
from verifier.websub.feed import parse_notification, VideoEvent
from verifier.websub.signature import is_valid_signature

GetChannelSecret = Callable[[str], Optional[str]]
OnVideo = Callable[[VideoEvent], None]


def process_notification(
    body: bytes, signature: Optional[str], *,
    get_channel_secret: GetChannelSecret, on_video: OnVideo,
) -> bool:
    event = parse_notification(body)
    if event is None:
        return False
    secret = get_channel_secret(event.channel_id)
    if secret is None:
        return False  # canal desconocido para nosotros
    if not is_valid_signature(body, signature, secret):
        return False
    on_video(event)
    return True
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_websub_callback.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/websub/callback.py backend/tests/test_websub_callback.py
git commit -m "feat: procesamiento puro de notificación WebSub"
```

---

## Tarea 5: Endpoint FastAPI (GET challenge + POST notificación)

**Files:**
- Create: `backend/verifier/websub/app.py`
- Test: `backend/tests/test_websub_app.py`

- [ ] **Step 1: Escribir el test que falla**

```python
import hashlib
import hmac
from fastapi.testclient import TestClient
from verifier.websub import app as appmod

FEED = b"""<?xml version="1.0"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry><yt:videoId>VID1</yt:videoId><yt:channelId>UC1</yt:channelId><title>t</title></entry>
</feed>"""


def test_get_challenge_is_echoed():
    client = TestClient(appmod.app)
    resp = client.get("/websub/callback", params={"hub.challenge": "abc123", "hub.mode": "subscribe"})
    assert resp.status_code == 200
    assert resp.text == "abc123"


def test_post_valid_notification_returns_204(monkeypatch):
    seen = []
    monkeypatch.setattr(appmod, "get_channel_secret", lambda chan: "s1")
    monkeypatch.setattr(appmod, "on_video", lambda ev: seen.append(ev.video_id))
    sig = "sha1=" + hmac.new(b"s1", FEED, hashlib.sha1).hexdigest()
    client = TestClient(appmod.app)
    resp = client.post("/websub/callback", content=FEED, headers={"X-Hub-Signature": sig})
    assert resp.status_code == 204
    assert seen == ["VID1"]


def test_post_bad_signature_returns_204_without_processing(monkeypatch):
    seen = []
    monkeypatch.setattr(appmod, "get_channel_secret", lambda chan: "s1")
    monkeypatch.setattr(appmod, "on_video", lambda ev: seen.append(ev.video_id))
    client = TestClient(appmod.app)
    resp = client.post("/websub/callback", content=FEED, headers={"X-Hub-Signature": "sha1=bad"})
    assert resp.status_code == 204
    assert seen == []  # no se procesó
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_websub_app.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/websub/app.py`**

```python
from __future__ import annotations
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from verifier.websub.callback import process_notification
from verifier.websub.feed import VideoEvent

app = FastAPI()


def get_channel_secret(channel_id: str) -> Optional[str]:
    """Reemplazable: busca en Supabase el websub_secret del canal.
    Por defecto no resuelve nada (se inyecta/monkeypatcha en producción y tests)."""
    return None


def on_video(event: VideoEvent) -> None:
    """Reemplazable: encola el procesamiento del video (dedup + asociación + transcript)."""
    return None


@app.get("/websub/callback", response_class=PlainTextResponse)
def verify(request: Request) -> str:
    # El hub valida con un GET que incluye hub.challenge -> se devuelve tal cual.
    return request.query_params.get("hub.challenge", "")


@app.post("/websub/callback")
async def receive(request: Request) -> Response:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature")
    process_notification(
        body, signature,
        get_channel_secret=get_channel_secret,
        on_video=on_video,
    )
    # Siempre 204 rápido: no revelamos al hub si validó o no.
    return Response(status_code=204)
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_websub_app.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/websub/app.py backend/tests/test_websub_app.py
git commit -m "feat: endpoint FastAPI de callback WebSub"
```

---

## Tarea 6: Asociación video → campaña(s)

Dado el `VideoEvent` (ya con metadata traída) y las campañas candidatas de la org del canal, devuelve las campañas cuyo link/código aparece en la descripción. Reusa los chequeos determinísticos de la Fase 1.

**Files:**
- Create: `backend/verifier/association.py`
- Test: `backend/tests/test_association.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import Brief, Requirement
from verifier.association import matching_campaigns, CandidateCampaign


def _campaign(cid, link=None, code=None):
    reqs = []
    if link:
        reqs.append(Requirement(code="R1", type="link_in_desc", spec={"expected_link": link}, method="deterministic"))
    if code:
        reqs.append(Requirement(code="R2", type="code_in_desc", spec={"code": code}, method="deterministic"))
    return CandidateCampaign(campaign_id=cid, brief=Brief(game_name="G", requirements=reqs))


def test_matches_by_link_or_code():
    desc = "Bajá el juego https://dl.game/x y usá GAMER20"
    candidates = [
        _campaign("c1", link="https://dl.game/x"),
        _campaign("c2", code="GAMER20"),
        _campaign("c3", link="https://otra.com/y"),  # no aparece
    ]
    matched = matching_campaigns(desc, candidates)
    assert set(matched) == {"c1", "c2"}


def test_no_match_returns_empty():
    matched = matching_campaigns("video sin nada", [_campaign("c1", link="https://dl.game/x")])
    assert matched == []
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_association.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/association.py`**

```python
from __future__ import annotations
from pydantic import BaseModel
from verifier.models import Brief
from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc


class CandidateCampaign(BaseModel):
    campaign_id: str
    brief: Brief


def _is_ad_for(description: str, brief: Brief) -> bool:
    for req in brief.requirements:
        if req.type == "link_in_desc":
            if check_link_in_desc(description, req.spec.get("expected_link", "")).met:
                return True
        elif req.type == "code_in_desc":
            if check_code_in_desc(description, req.spec.get("code", "")).met:
                return True
    return False


def matching_campaigns(description: str, candidates: list[CandidateCampaign]) -> list[str]:
    return [c.campaign_id for c in candidates if _is_ad_for(description, c.brief)]
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_association.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/association.py backend/tests/test_association.py
git commit -m "feat: asociación video -> campaña(s) por link/código"
```

---

## Tarea 7: Scheduling de backoff del transcript

Implementa la sección 5.4 del diseño: decidir el próximo estado y `next_retry_at` de un video según los intentos y el tiempo transcurrido. Función pura (recibe `now` para testear).

**Files:**
- Create: `backend/verifier/jobs/backoff.py`
- Test: `backend/tests/test_jobs_backoff.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from datetime import datetime, timedelta, timezone
from verifier.jobs.backoff import plan_transcript_attempt, AttemptResult

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)


def test_transcript_available_goes_to_verifying():
    r = plan_transcript_attempt(detected_at=NOW, attempts=0, transcript_available=True, now=NOW)
    assert r.status == "verifying"
    assert r.next_retry_at is None


def test_not_available_schedules_backoff():
    r = plan_transcript_attempt(detected_at=NOW, attempts=0, transcript_available=False, now=NOW)
    assert r.status == "awaiting_transcript"
    assert r.attempts == 1
    assert r.next_retry_at == NOW + timedelta(minutes=15)


def test_second_attempt_uses_next_step():
    r = plan_transcript_attempt(detected_at=NOW, attempts=1, transcript_available=False, now=NOW)
    assert r.next_retry_at == NOW + timedelta(minutes=30)


def test_timeout_goes_to_needs_human():
    late = NOW + timedelta(hours=25)
    r = plan_transcript_attempt(detected_at=NOW, attempts=6, transcript_available=False, now=late)
    assert r.status == "needs_human"
    assert r.next_retry_at is None
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_jobs_backoff.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/jobs/backoff.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

BACKOFF_SCHEDULE_MIN = [15, 30, 60, 120, 240, 480]
MAX_WAIT_HOURS = 24


class AttemptResult(BaseModel):
    status: str
    attempts: int
    next_retry_at: Optional[datetime] = None


def _next_delay_min(attempts: int) -> int:
    idx = min(attempts, len(BACKOFF_SCHEDULE_MIN) - 1)
    return BACKOFF_SCHEDULE_MIN[idx]


def plan_transcript_attempt(
    *, detected_at: datetime, attempts: int, transcript_available: bool, now: datetime
) -> AttemptResult:
    if transcript_available:
        return AttemptResult(status="verifying", attempts=attempts, next_retry_at=None)
    elapsed_h = (now - detected_at).total_seconds() / 3600
    if elapsed_h >= MAX_WAIT_HOURS:
        return AttemptResult(status="needs_human", attempts=attempts, next_retry_at=None)
    delay = _next_delay_min(attempts)
    return AttemptResult(
        status="awaiting_transcript",
        attempts=attempts + 1,
        next_retry_at=now + timedelta(minutes=delay),
    )
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_jobs_backoff.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/jobs/backoff.py backend/tests/test_jobs_backoff.py
git commit -m "feat: scheduling de backoff del transcript"
```

---

## Tarea 8: Renovación de leases WebSub

Selecciona canales activos cuya suscripción está por vencer y los vuelve a suscribir. La obtención y el envío se inyectan para testear.

**Files:**
- Create: `backend/verifier/jobs/leases.py`
- Test: `backend/tests/test_jobs_leases.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from datetime import datetime, timedelta, timezone
from verifier.jobs.leases import renew_expiring_leases, ChannelLease

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)


def test_renews_only_expiring_within_window():
    channels = [
        ChannelLease(channel_id="UC1", secret="s1", lease_expires_at=NOW + timedelta(hours=12)),  # vence pronto
        ChannelLease(channel_id="UC2", secret="s2", lease_expires_at=NOW + timedelta(days=5)),     # lejos
    ]
    sent = []
    n = renew_expiring_leases(
        channels, now=NOW, within=timedelta(days=1),
        resubscribe=lambda ch: sent.append(ch.channel_id) or True,
    )
    assert n == 1
    assert sent == ["UC1"]


def test_counts_only_successful():
    channels = [ChannelLease(channel_id="UC1", secret="s1", lease_expires_at=NOW)]
    n = renew_expiring_leases(channels, now=NOW, within=timedelta(days=1), resubscribe=lambda ch: False)
    assert n == 0
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_jobs_leases.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/jobs/leases.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Callable
from pydantic import BaseModel


class ChannelLease(BaseModel):
    channel_id: str
    secret: str
    lease_expires_at: datetime


Resubscribe = Callable[[ChannelLease], bool]


def renew_expiring_leases(
    channels: list[ChannelLease], *, now: datetime, within: timedelta, resubscribe: Resubscribe
) -> int:
    renewed = 0
    cutoff = now + within
    for ch in channels:
        if ch.lease_expires_at <= cutoff:
            if resubscribe(ch):
                renewed += 1
    return renewed
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_jobs_leases.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/jobs/leases.py backend/tests/test_jobs_leases.py
git commit -m "feat: renovación de leases WebSub"
```

---

## Tarea 9: Revisor de plazos

Marca `failed` los `campaign_channel` en `pending` de campañas con plazo vencido **que no tienen ninguna verificación** (nunca apareció la publi). Una publi en `review` no se falla. Función pura sobre filas mockeadas.

**Files:**
- Create: `backend/verifier/jobs/deadlines.py`
- Test: `backend/tests/test_jobs_deadlines.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from datetime import date
from verifier.jobs.deadlines import channels_to_fail, ChannelDeadlineRow

TODAY = date(2026, 6, 17)


def test_fails_pending_overdue_without_verification():
    rows = [
        ChannelDeadlineRow(campaign_channel_id="cc1", status="pending", ends_at=date(2026, 6, 10), has_verification=False),  # vencido, sin publi -> fail
        ChannelDeadlineRow(campaign_channel_id="cc2", status="pending", ends_at=date(2026, 6, 10), has_verification=True),   # tiene publi (review) -> no fail
        ChannelDeadlineRow(campaign_channel_id="cc3", status="pending", ends_at=date(2026, 6, 20), has_verification=False),  # plazo abierto -> no fail
        ChannelDeadlineRow(campaign_channel_id="cc4", status="verified", ends_at=date(2026, 6, 1), has_verification=True),   # ya verificado -> no toca
    ]
    assert channels_to_fail(rows, today=TODAY) == ["cc1"]
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_jobs_deadlines.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/jobs/deadlines.py`**

```python
from __future__ import annotations
from datetime import date
from pydantic import BaseModel


class ChannelDeadlineRow(BaseModel):
    campaign_channel_id: str
    status: str
    ends_at: date
    has_verification: bool


def channels_to_fail(rows: list[ChannelDeadlineRow], *, today: date) -> list[str]:
    return [
        r.campaign_channel_id
        for r in rows
        if r.status == "pending" and r.ends_at < today and not r.has_verification
    ]
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_jobs_deadlines.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Correr toda la suite**

Run: `pytest -q`
Expected: PASS (Fases 1 + 2 + 3).

- [ ] **Step 6: Commit**

```bash
git add backend/verifier/jobs/deadlines.py backend/tests/test_jobs_deadlines.py
git commit -m "feat: revisor de plazos (pending sin verificación -> failed)"
```

---

## Tarea 10: Verificación multi-campaña reutilizando el transcript

Un video puede ser la publi de varias campañas (diseño 5.5): se baja el transcript **una sola vez** y se verifica contra cada brief. Reusa `evaluate` de la Fase 1 (núcleo sin fetch).

**Files:**
- Create: `backend/verifier/verify_multi.py`
- Test: `backend/tests/test_verify_multi.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.models import Brief, Requirement, VideoMetadata, Transcript, TranscriptSegment, RequirementResult
from verifier.verify_multi import verify_campaigns


def _brief(link):
    return Brief(game_name="G", requirements=[
        Requirement(code="R1", type="link_in_desc", spec={"expected_link": link}, method="deterministic", required=True),
    ])


def test_verifies_each_campaign_reusing_transcript(mocker):
    md = VideoMetadata(video_id="v", description="https://dl.game/a")
    transcript = Transcript(segments=[TranscriptSegment(text="texto", start=0.0, duration=1.0)])
    provider = mocker.Mock()
    provider.get_transcript.return_value = transcript
    llm = mocker.Mock(return_value=[])

    briefs = {"c1": _brief("https://dl.game/a"), "c2": _brief("https://dl.game/b")}
    out = verify_campaigns(
        "v", briefs,
        metadata_client=lambda vid: md,
        transcript_provider=provider,
        llm_check=llm,
    )
    assert out["c1"].overall_status == "pass"   # el link de c1 aparece
    assert out["c2"].overall_status == "fail"   # el de c2 no
    provider.get_transcript.assert_called_once_with("v")  # transcript una sola vez
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_verify_multi.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/verify_multi.py`**

```python
from __future__ import annotations
from typing import Callable
from verifier.models import Brief, Verification, VideoMetadata
from verifier.verify import evaluate, MetadataClient, LLMCheck


def verify_campaigns(
    video_id: str,
    briefs_by_campaign: dict[str, Brief],
    *,
    metadata_client: MetadataClient,
    transcript_provider,
    llm_check: LLMCheck,
) -> dict[str, Verification]:
    metadata: VideoMetadata = metadata_client(video_id)
    needs_transcript = any(
        any(r.method == "llm" for r in b.requirements) for b in briefs_by_campaign.values()
    )
    transcript = transcript_provider.get_transcript(video_id) if needs_transcript else None
    return {
        campaign_id: evaluate(brief, metadata, transcript, llm_check=llm_check)
        for campaign_id, brief in briefs_by_campaign.items()
    }
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_verify_multi.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add backend/verifier/verify_multi.py backend/tests/test_verify_multi.py
git commit -m "feat: verificación multi-campaña reutilizando el transcript"
```

---

## Tarea 11: Mapeo del veredicto al estado del `campaign_channel`

Traduce el `overall_status` de una verificación al estado del influencer, con la precedencia del diseño (5.5): `verified > incomplete > pending`. Una vez `verified`, no retrocede; un `fail` lo deja `incomplete` (puede mejorar a `verified` si re-suben); un `review` no cambia el estado (sigue esperando / cola humana).

**Files:**
- Create: `backend/verifier/channel_status.py`
- Test: `backend/tests/test_channel_status.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from verifier.channel_status import next_channel_status


def test_pass_sets_verified():
    assert next_channel_status("pending", "pass") == "verified"


def test_fail_sets_incomplete():
    assert next_channel_status("pending", "fail") == "incomplete"


def test_review_keeps_current():
    assert next_channel_status("pending", "review") == "pending"
    assert next_channel_status("incomplete", "review") == "incomplete"


def test_verified_never_regresses():
    assert next_channel_status("verified", "fail") == "verified"
    assert next_channel_status("verified", "review") == "verified"


def test_incomplete_can_upgrade_to_verified():
    assert next_channel_status("incomplete", "pass") == "verified"
```

- [ ] **Step 2: Correr el test para ver que falla**

Run: `pytest tests/test_channel_status.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `backend/verifier/channel_status.py`**

```python
from __future__ import annotations
from verifier.models import OverallStatus

ChannelStatus = str  # 'pending' | 'verified' | 'incomplete' | 'failed'


def next_channel_status(current: ChannelStatus, verdict: OverallStatus) -> ChannelStatus:
    """Aplica una verificación al estado del campaign_channel.
    Precedencia: verified > incomplete > pending. 'failed' lo decide el revisor de plazos."""
    if current == "verified":
        return "verified"  # estado ganador, no retrocede
    if verdict == "pass":
        return "verified"
    if verdict == "fail":
        return "incomplete"
    # verdict == "review": no cambia (sigue esperando / cola humana)
    return current
```

- [ ] **Step 4: Correr el test para ver que pasa**

Run: `pytest tests/test_channel_status.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Correr toda la suite**

Run: `pytest -q`
Expected: PASS (Fases 1 + 2 + 3 completas).

- [ ] **Step 6: Commit**

```bash
git add backend/verifier/channel_status.py backend/tests/test_channel_status.py
git commit -m "feat: mapeo veredicto -> estado del campaign_channel (precedencia)"
```

---

## Validación de la fase (criterios de salida)

- [ ] `pytest -q` pasa completo desde `backend/`.
- [ ] El endpoint responde el `hub.challenge` en el GET y procesa el POST validando la firma.
- [ ] Con un túnel público (ngrok), una suscripción real a un canal de prueba dispara el callback al subir un video.
- [ ] El backoff agenda los reintentos según el cronograma y cae a `needs_human` tras 24 h.
- [ ] El revisor de plazos no marca `failed` un canal con una publi en `review`.

## Notas / riesgos a confirmar al implementar

- **Cableado contra Supabase:** `get_channel_secret`, `on_video`, y los jobs (backoff/leases/deadlines) acá quedan como lógica pura/inyectable. Conectarlos al repositorio Supabase (service_role) es trabajo de integración a hacer junto con la Fase 4; los tests no tocan la base.
- **Endpoint público:** el callback debe ser accesible desde internet (TLS). En local usar ngrok; en prod, la URL pública del servicio Python.
- **Dedup por `videoId`:** el feed dispara también en ediciones de título/descripción → el `on_video` debe ser idempotente (apoyarse en `unique (org_id, youtube_video_id)` del schema).
- **`hub.verify`:** el modo `async` hace que el hub valide con un GET posterior; confirmar el comportamiento contra la doc vigente de YouTube/PubSubHubbub.
- **Multi-tenant:** un mismo canal puede estar en varias orgs → al procesar el evento hay que abrir un `video_submission` por cada org que monitorea ese canal (ver diseño, sección 4).
