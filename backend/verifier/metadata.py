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
