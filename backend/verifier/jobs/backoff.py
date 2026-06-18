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
