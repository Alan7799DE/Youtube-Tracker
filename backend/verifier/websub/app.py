from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from verifier.websub.callback import process_notification
from verifier.websub.feed import VideoEvent

router = APIRouter()


def get_channel_secret(channel_id: str) -> Optional[str]:
    """Reemplazable: busca en Supabase el websub_secret del canal.
    Por defecto no resuelve nada (se inyecta/monkeypatcha en producción y tests)."""
    return None


def on_video(event: VideoEvent) -> None:
    """Reemplazable: encola el procesamiento del video (dedup + asociación + transcript)."""
    return None


@router.get("/websub/callback", response_class=PlainTextResponse)
def verify(request: Request) -> str:
    # El hub valida con un GET que incluye hub.challenge -> se devuelve tal cual.
    return request.query_params.get("hub.challenge", "")


@router.post("/websub/callback")
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


# app local para testear este módulo en aislamiento; en producción se compone
# junto con la API en verifier/server.py (ver docs/requisitos-despliegue.md).
app = FastAPI()
app.include_router(router)
