"""Transcript provider abstraction for the YouTube ad-verifier.

Targets youtube-transcript-api 1.x (tested with 1.2.4).

In v1.x the API is instance-based:
    YouTubeTranscriptApi().fetch(video_id, languages=[...])
returning a FetchedTranscript whose snippets are iterable objects with
.text / .start / .duration attributes (not dicts as in the old 0.x API).
"""
from __future__ import annotations

from typing import Optional, Protocol

from youtube_transcript_api import YouTubeTranscriptApi

from verifier.models import Transcript, TranscriptSegment


class TranscriptProvider(Protocol):
    def get_transcript(self, video_id: str) -> Optional[Transcript]: ...


class YouTubeTranscriptProvider:
    def __init__(self, languages: tuple[str, ...] = ("es", "en")):
        self.languages = languages

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            # v1.x: instance method; snippets are attribute-style objects
            raw = YouTubeTranscriptApi().fetch(video_id, languages=list(self.languages))
        except Exception:
            return None

        segments = [
            TranscriptSegment(text=s.text, start=float(s.start), duration=float(s.duration))
            for s in raw
        ]
        return Transcript(language=self.languages[0], source="youtube_auto", segments=segments)
