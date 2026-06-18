import hashlib
import hmac
from fastapi.testclient import TestClient
from verifier.websub import app as appmod

FEED = b"""<?xml version="1.0"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry><yt:videoId>VID1</yt:videoId><yt:channelId>UC1</yt:channelId><title>t</title></entry>
</feed>"""


def test_get_challenge_is_echoed():
    client = TestClient(appmod.app)
    resp = client.get("/websub/callback", params={"hub.challenge": "abc123", "hub.mode": "subscribe"})
    assert resp.status_code == 200
    assert resp.text == "abc123"


def test_post_valid_notification_returns_204(monkeypatch):
    seen = []
    monkeypatch.setattr(appmod, "get_channel_secret", lambda chan: "s1")
    monkeypatch.setattr(appmod, "on_video", lambda ev: seen.append(ev.video_id))
    sig = "sha1=" + hmac.new(b"s1", FEED, hashlib.sha1).hexdigest()
    client = TestClient(appmod.app)
    resp = client.post("/websub/callback", content=FEED, headers={"X-Hub-Signature": sig})
    assert resp.status_code == 204
    assert seen == ["VID1"]


def test_post_bad_signature_returns_204_without_processing(monkeypatch):
    seen = []
    monkeypatch.setattr(appmod, "get_channel_secret", lambda chan: "s1")
    monkeypatch.setattr(appmod, "on_video", lambda ev: seen.append(ev.video_id))
    client = TestClient(appmod.app)
    resp = client.post("/websub/callback", content=FEED, headers={"X-Hub-Signature": "sha1=bad"})
    assert resp.status_code == 204
    assert seen == []  # no se procesó
