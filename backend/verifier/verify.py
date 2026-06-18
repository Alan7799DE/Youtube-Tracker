from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Optional
from verifier.models import Brief, Verification, VideoMetadata, Transcript, RequirementResult
from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc
from verifier.decision import decide

if TYPE_CHECKING:
    from verifier.transcript import TranscriptProvider

MetadataClient = Callable[[str], VideoMetadata]
LLMCheck = Callable[[Brief, str], list[RequirementResult]]


def _run_deterministic(brief: Brief, description: str) -> list[RequirementResult]:
    out: list[RequirementResult] = []
    for req in brief.requirements:
        if req.type == "link_in_desc":
            out.append(check_link_in_desc(description, req.spec.get("expected_link", ""), code=req.code))
        elif req.type == "code_in_desc":
            out.append(check_code_in_desc(description, req.spec.get("code", ""), code=req.code))
    return out


def evaluate_brief(
    brief: Brief, metadata: VideoMetadata, transcript: Optional[Transcript], *, llm_check: LLMCheck
) -> Verification:
    """Núcleo de verificación SIN fetch: recibe metadata y transcript ya obtenidos.
    Reutilizable para verificar varias campañas con un mismo transcript (Fase 3)."""
    results = _run_deterministic(brief, metadata.description)
    has_llm = any(r.method == "llm" for r in brief.requirements)
    if has_llm:
        if transcript is None:
            # Sin transcript no se pueden correr R3/R4 -> a revisión humana.
            return Verification(overall_status="review", results=results)
        results += llm_check(brief, transcript.full_text())
    status = decide(results, brief.requirements)
    return Verification(overall_status=status, results=results)


def verify_video(
    video_id: str,
    brief: Brief,
    *,
    metadata_client: MetadataClient,
    transcript_provider: "TranscriptProvider",
    llm_check: LLMCheck,
) -> Verification:
    metadata = metadata_client(video_id)
    has_llm = any(r.method == "llm" for r in brief.requirements)
    transcript = transcript_provider.get_transcript(video_id) if has_llm else None
    return evaluate_brief(brief, metadata, transcript, llm_check=llm_check)
