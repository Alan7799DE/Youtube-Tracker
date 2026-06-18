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
