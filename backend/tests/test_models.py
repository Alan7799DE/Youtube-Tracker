from verifier.models import (
    Requirement, Brief, VideoMetadata, TranscriptSegment, Transcript,
    RequirementResult, Verification,
)


def test_transcript_full_text_joins_segments():
    t = Transcript(
        language="es",
        source="youtube_auto",
        segments=[
            TranscriptSegment(text="hola", start=0.0, duration=1.0),
            TranscriptSegment(text="mundo", start=1.0, duration=1.0),
        ],
    )
    assert t.full_text() == "hola mundo"


def test_brief_requirement_lookup_by_type():
    brief = Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R1", type="link_in_desc",
                        spec={"expected_link": "https://dl.game/x"},
                        method="deterministic", required=True),
        ],
    )
    assert brief.requirements[0].spec["expected_link"] == "https://dl.game/x"


def test_verification_holds_results():
    v = Verification(
        overall_status="pass",
        results=[RequirementResult(requirement_code="R1", met=True, method="deterministic")],
    )
    assert v.overall_status == "pass"
    assert v.results[0].met is True
