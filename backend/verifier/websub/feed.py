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
