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
