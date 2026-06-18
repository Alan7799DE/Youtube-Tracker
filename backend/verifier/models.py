from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

RequirementType = Literal[
    "link_in_desc", "code_in_desc", "mention_name", "describe_game", "show_gameplay"
]
Method = Literal["deterministic", "llm", "human"]
OverallStatus = Literal["pass", "fail", "review"]


class Requirement(BaseModel):
    code: str
    type: RequirementType
    spec: dict = Field(default_factory=dict)
    method: Method
    required: bool = True


class Brief(BaseModel):
    game_name: str
    requirements: list[Requirement]


class VideoMetadata(BaseModel):
    video_id: str
    title: str = ""
    description: str = ""
    channel_id: str = ""
    published_at: Optional[str] = None
    duration: Optional[str] = None


class TranscriptSegment(BaseModel):
    text: str
    start: float
    duration: float


class Transcript(BaseModel):
    language: Optional[str] = None
    source: str = "youtube_auto"
    segments: list[TranscriptSegment]

    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()


class RequirementResult(BaseModel):
    requirement_code: str
    met: bool
    confidence: Optional[float] = None
    method: Optional[Method] = None
    evidence: Optional[str] = None
    evidence_timestamp_s: Optional[int] = None
    reasoning: Optional[str] = None


class Verification(BaseModel):
    overall_status: OverallStatus
    results: list[RequirementResult]
    model: Optional[str] = None
    raw_output: Optional[dict] = None
