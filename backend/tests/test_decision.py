from verifier.models import Requirement, RequirementResult
from verifier.decision import decide

LINK = Requirement(code="R1", type="link_in_desc", spec={}, method="deterministic", required=True)
GAME = Requirement(code="R3", type="mention_name", spec={}, method="llm", required=True)
PLAY = Requirement(code="R5", type="show_gameplay", spec={}, method="human", required=True)


def test_deterministic_required_fail_is_fail():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=False, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm"),
    ]
    assert decide(results, reqs) == "fail"


def test_all_met_no_visual_is_pass():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.9, method="llm"),
    ]
    assert decide(results, reqs) == "pass"


def test_all_met_with_pending_visual_is_review():
    reqs = [LINK, GAME, PLAY]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.9, method="llm"),
    ]
    assert decide(results, reqs) == "review"


def test_low_confidence_llm_is_review():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.6, method="llm"),
    ]
    assert decide(results, reqs) == "review"


def test_llm_required_not_met_high_confidence_is_fail():
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=False, confidence=0.95, method="llm"),
    ]
    assert decide(results, reqs) == "fail"


def test_llm_not_met_low_confidence_is_review():
    # Ante la duda, REVIEW: un "no cumple" con baja confianza no debe ser FAIL.
    reqs = [LINK, GAME]
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R3", met=False, confidence=0.4, method="llm"),
    ]
    assert decide(results, reqs) == "review"
