"""Tests for TranscriptProvider — targets youtube-transcript-api 1.x.

The v1.x API uses instance-based fetch:
    YouTubeTranscriptApi().fetch(video_id, languages=[...])
returning a FetchedTranscript whose snippets are iterable objects with
.text / .start / .duration attributes (not dicts).
"""
from types import SimpleNamespace

from verifier.transcript import YouTubeTranscriptProvider
from verifier.models import Transcript


def _make_snippets(*args):
    """Build a list of SimpleNamespace snippet objects matching FetchedTranscriptSnippet."""
    return [SimpleNamespace(text=text, start=start, duration=duration) for text, start, duration in args]


def test_provider_maps_raw_segments(mocker):
    fake_snippets = _make_snippets(
        ("hoy traigo Mystic Realms", 1.2, 2.0),
        ("un RPG enorme", 3.2, 1.5),
    )
    # Patch the instance-level fetch method on the class
    fetch = mocker.patch(
        "verifier.transcript.YouTubeTranscriptApi.fetch",
        return_value=fake_snippets,
    )
    provider = YouTubeTranscriptProvider()
    t = provider.get_transcript("vid123")

    assert isinstance(t, Transcript)
    assert t.full_text() == "hoy traigo Mystic Realms un RPG enorme"
    assert t.segments[0].start == 1.2
    fetch.assert_called_once_with("vid123", languages=["es", "en"])


def test_provider_returns_none_when_unavailable(mocker):
    mocker.patch(
        "verifier.transcript.YouTubeTranscriptApi.fetch",
        side_effect=Exception("TranscriptsDisabled"),
    )
    provider = YouTubeTranscriptProvider()
    assert provider.get_transcript("vid123") is None
