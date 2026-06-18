from __future__ import annotations
from verifier.models import Brief, Verification, VideoMetadata
from verifier.verify import evaluate_brief, MetadataClient, LLMCheck


def verify_campaigns(
    video_id: str,
    briefs_by_campaign: dict[str, Brief],
    *,
    metadata_client: MetadataClient,
    transcript_provider,
    llm_check: LLMCheck,
) -> dict[str, Verification]:
    metadata: VideoMetadata = metadata_client(video_id)
    needs_transcript = any(
        any(r.method == "llm" for r in b.requirements) for b in briefs_by_campaign.values()
    )
    transcript = transcript_provider.get_transcript(video_id) if needs_transcript else None
    return {
        campaign_id: evaluate_brief(brief, metadata, transcript, llm_check=llm_check)
        for campaign_id, brief in briefs_by_campaign.items()
    }
