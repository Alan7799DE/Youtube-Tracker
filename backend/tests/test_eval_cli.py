import io

from verifier.models import Brief, Verification
from verifier.eval import GoldenCase
from verifier.eval_cli import EvalRunResult, build_real_runner, run_eval


def _case(video_id, expected):
    return GoldenCase(
        video_id=video_id,
        expected_overall=expected,
        brief=Brief(game_name="G", requirements=[]),
    )


def test_run_eval_counts_correct_and_false_pass():
    cases = [
        _case("a", "fail"),  # el sistema dirá pass -> falso PASS
        _case("b", "pass"),  # el sistema dirá pass -> correcto
        _case("c", "review"),  # el sistema dirá review -> correcto
    ]

    def fake_runner(video_id, brief):
        status = "review" if video_id == "c" else "pass"
        return Verification(overall_status=status, results=[])

    out = io.StringIO()
    result = run_eval(cases, fake_runner, out=out)

    assert result.total == 3
    assert result.correct == 2
    assert result.false_pass == 1
    assert result.errors == 0
    assert result.exit_code == 1  # hubo un falso PASS
    text = out.getvalue()
    assert "FALSO PASS" in text


def test_run_eval_counts_errors_and_keeps_going():
    cases = [_case("boom", "pass"), _case("ok", "pass")]

    def fake_runner(video_id, brief):
        if video_id == "boom":
            raise RuntimeError("sin transcript")
        return Verification(overall_status="pass", results=[])

    out = io.StringIO()
    result = run_eval(cases, fake_runner, out=out)

    assert result.errors == 1
    assert result.correct == 1
    assert result.exit_code == 1
    assert "ERROR" in out.getvalue()


def test_exit_code_zero_when_clean():
    r = EvalRunResult(total=2, correct=2, false_pass=0, errors=0)
    assert r.exit_code == 0


def test_build_real_runner_wires_metadata_transcript_and_llm(mocker):
    from verifier.models import VideoMetadata, Transcript, TranscriptSegment, RequirementResult

    meta = mocker.patch(
        "verifier.metadata.fetch_video_metadata",
        return_value=VideoMetadata(video_id="v1", description="bajá en https://dl/x"),
    )
    transcript = Transcript(segments=[TranscriptSegment(text="hola", start=0.0, duration=1.0)])
    mocker.patch(
        "verifier.transcript.YouTubeTranscriptProvider.get_transcript",
        return_value=transcript,
    )
    llm = mocker.patch(
        "verifier.checks.llm.check_requirements_llm",
        return_value=[
            RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm")
        ],
    )

    brief = Brief.model_validate(
        {
            "game_name": "G",
            "requirements": [
                {"code": "R3", "type": "mention_name", "spec": {"game_name": "G"}, "method": "llm"}
            ],
        }
    )
    runner = build_real_runner(
        youtube_key="yt", openai_client=object(), model="gpt-4o-mini"
    )
    verification = runner("v1", brief)

    assert verification.overall_status == "pass"
    meta.assert_called_once()
    llm.assert_called_once()
