from datetime import date
from verifier.jobs.deadlines import channels_to_fail, ChannelDeadlineRow

TODAY = date(2026, 6, 17)


def test_fails_pending_overdue_without_verification():
    rows = [
        ChannelDeadlineRow(campaign_channel_id="cc1", status="pending", ends_at=date(2026, 6, 10), has_verification=False),  # vencido, sin publi -> fail
        ChannelDeadlineRow(campaign_channel_id="cc2", status="pending", ends_at=date(2026, 6, 10), has_verification=True),   # tiene publi (review) -> no fail
        ChannelDeadlineRow(campaign_channel_id="cc3", status="pending", ends_at=date(2026, 6, 20), has_verification=False),  # plazo abierto -> no fail
        ChannelDeadlineRow(campaign_channel_id="cc4", status="verified", ends_at=date(2026, 6, 1), has_verification=True),   # ya verificado -> no toca
    ]
    assert channels_to_fail(rows, today=TODAY) == ["cc1"]
