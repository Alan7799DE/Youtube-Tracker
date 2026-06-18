from datetime import datetime, timedelta, timezone
from verifier.jobs.leases import renew_expiring_leases, ChannelLease

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)


def test_renews_only_expiring_within_window():
    channels = [
        ChannelLease(channel_id="UC1", secret="s1", lease_expires_at=NOW + timedelta(hours=12)),  # vence pronto
        ChannelLease(channel_id="UC2", secret="s2", lease_expires_at=NOW + timedelta(days=5)),     # lejos
    ]
    sent = []
    n = renew_expiring_leases(
        channels, now=NOW, within=timedelta(days=1),
        resubscribe=lambda ch: sent.append(ch.channel_id) or True,
    )
    assert n == 1
    assert sent == ["UC1"]


def test_counts_only_successful():
    channels = [ChannelLease(channel_id="UC1", secret="s1", lease_expires_at=NOW)]
    n = renew_expiring_leases(channels, now=NOW, within=timedelta(days=1), resubscribe=lambda ch: False)
    assert n == 0
