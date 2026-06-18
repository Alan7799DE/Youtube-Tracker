from verifier.models import Verification
from verifier.eval import evaluate, GoldenCase, Brief


def test_evaluate_counts_false_pass(mocker):
    cases = [
        GoldenCase(video_id="a", expected_overall="fail",
                   brief=Brief(game_name="G", requirements=[])),
        GoldenCase(video_id="b", expected_overall="pass",
                   brief=Brief(game_name="G", requirements=[])),
    ]

    def fake_runner(video_id, brief):
        if video_id == "a":
            return Verification(overall_status="pass", results=[])  # falso PASS
        return Verification(overall_status="pass", results=[])

    report = evaluate(cases, runner=fake_runner)
    assert report.total == 2
    assert report.false_pass == 1
    assert report.correct == 1
