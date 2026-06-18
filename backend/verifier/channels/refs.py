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
