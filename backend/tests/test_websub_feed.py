from verifier.websub.feed import parse_notification, VideoEvent

FEED = b"""<?xml version="1.0"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>VID123</yt:videoId>
    <yt:channelId>UC456</yt:channelId>
    <title>Mi video</title>
  </entry>
</feed>"""


def test_parse_extracts_ids():
    ev = parse_notification(FEED)
    assert ev == VideoEvent(video_id="VID123", channel_id="UC456", title="Mi video")


def test_parse_returns_none_without_entry():
    body = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert parse_notification(body) is None
