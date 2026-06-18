from verifier.models import (
    Brief, Requirement, VideoMetadata, Transcript, TranscriptSegment, RequirementResult,
)
from verifier.verify_multi import verify_campaigns


def _brief(link):
    # Incluye un requisito LLM para que el transcript sea necesario: así se ejercita
    # la reutilización del transcript entre campañas (diseño 5.5).
    return Brief(game_name="G", requirements=[
        Requirement(code="R1", type="link_in_desc", spec={"expected_link": link}, method="deterministic", required=True),
        Requirement(code="R3", type="mention_name", spec={}, method="llm", required=True),
    ])


def test_verifies_each_campaign_reusing_transcript(mocker):
    md = VideoMetadata(video_id="v", description="https://dl.game/a")
    transcript = Transcript(segments=[TranscriptSegment(text="texto", start=0.0, duration=1.0)])
    provider = mocker.Mock()
    provider.get_transcript.return_value = transcript
    llm = mocker.Mock(return_value=[
        RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm"),
    ])

    briefs = {"c1": _brief("https://dl.game/a"), "c2": _brief("https://dl.game/b")}
    out = verify_campaigns(
        "v", briefs,
        metadata_client=lambda vid: md,
        transcript_provider=provider,
        llm_check=llm,
    )
    assert out["c1"].overall_status == "pass"   # el link de c1 aparece
    assert out["c2"].overall_status == "fail"   # el de c2 no
    provider.get_transcript.assert_called_once_with("v")  # transcript una sola vez
