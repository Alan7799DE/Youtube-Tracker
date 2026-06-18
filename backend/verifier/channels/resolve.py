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
