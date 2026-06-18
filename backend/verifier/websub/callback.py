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
