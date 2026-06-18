from verifier.models import Brief, Requirement, VideoMetadata, Transcript, TranscriptSegment, RequirementResult
from verifier.verify import verify_video


def _brief():
    return Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R1", type="link_in_desc", spec={"expected_link": "https://dl.game/x"}, method="deterministic", required=True),
            Requirement(code="R2", type="code_in_desc", spec={"code": "GAMER20"}, method="deterministic", required=True),
            Requirement(code="R3", type="mention_name", spec={"game_name": "Mystic Realms"}, method="llm", required=True),
        ],
    )


def test_full_pass(mocker):
    md = VideoMetadata(video_id="v", title="t", description="https://dl.game/x GAMER20", channel_id="UC")
    transcript = Transcript(segments=[TranscriptSegment(text="traigo Mystic Realms", start=10.0, duration=2.0)])

    metadata_client = mocker.Mock(return_value=md)
    provider = mocker.Mock()
    provider.get_transcript.return_value = transcript
    llm = mocker.Mock(return_value=[
        RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm"),
    ])

    v = verify_video("v", _brief(), metadata_client=metadata_client, transcript_provider=provider, llm_check=llm)
    assert v.overall_status == "pass"
    assert {r.requirement_code for r in v.results} == {"R1", "R2", "R3"}


def test_missing_transcript_goes_to_review(mocker):
    md = VideoMetadata(video_id="v", title="t", description="https://dl.game/x GAMER20", channel_id="UC")
    metadata_client = mocker.Mock(return_value=md)
    provider = mocker.Mock()
    provider.get_transcript.return_value = None
    llm = mocker.Mock()

    v = verify_video("v", _brief(), metadata_client=metadata_client, transcript_provider=provider, llm_check=llm)
    assert v.overall_status == "review"
    llm.assert_not_called()
