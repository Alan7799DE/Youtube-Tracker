import hashlib
import hmac
from verifier.websub.callback import process_notification

FEED = b"""<?xml version="1.0"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry><yt:videoId>VID1</yt:videoId><yt:channelId>UC1</yt:channelId><title>t</title></entry>
</feed>"""


def _sig(body, secret):
    return "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()


def test_valid_notification_invokes_callback():
    seen = []
    ok = process_notification(
        FEED, _sig(FEED, "s1"),
        get_channel_secret=lambda chan: "s1" if chan == "UC1" else None,
        on_video=lambda ev: seen.append((ev.channel_id, ev.video_id)),
    )
    assert ok is True
    assert seen == [("UC1", "VID1")]


def test_bad_signature_is_rejected():
    seen = []
    ok = process_notification(
        FEED, "sha1=bad",
        get_channel_secret=lambda chan: "s1",
        on_video=lambda ev: seen.append(ev),
    )
    assert ok is False
    assert seen == []


def test_unknown_channel_is_ignored():
    ok = process_notification(
        FEED, _sig(FEED, "s1"),
        get_channel_secret=lambda chan: None,
        on_video=lambda ev: None,
    )
    assert ok is False
