from verifier.metadata import fetch_video_metadata
from verifier.models import VideoMetadata


def test_fetch_parses_snippet_and_details(mocker):
    payload = {
        "items": [{
            "snippet": {
                "title": "Jugando Mystic Realms",
                "description": "Link https://dl.game/x código GAMER20",
                "channelId": "UC_abc",
                "publishedAt": "2026-06-01T10:00:00Z",
            },
            "contentDetails": {"duration": "PT12M30S"},
        }]
    }
    resp = mocker.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    mocker.patch("verifier.metadata.requests.get", return_value=resp)

    md = fetch_video_metadata("vid123", api_key="KEY")
    assert isinstance(md, VideoMetadata)
    assert md.title == "Jugando Mystic Realms"
    assert md.channel_id == "UC_abc"
    assert md.duration == "PT12M30S"


def test_fetch_raises_when_no_items(mocker):
    resp = mocker.Mock()
    resp.json.return_value = {"items": []}
    resp.raise_for_status.return_value = None
    mocker.patch("verifier.metadata.requests.get", return_value=resp)
    try:
        fetch_video_metadata("missing", api_key="KEY")
        assert False, "debería haber lanzado"
    except ValueError:
        pass
