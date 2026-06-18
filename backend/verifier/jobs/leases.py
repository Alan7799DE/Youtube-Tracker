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
