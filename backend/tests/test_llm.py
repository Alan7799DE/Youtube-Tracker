from verifier.models import Brief, Requirement, Transcript, TranscriptSegment
from verifier.checks.llm import LLMOutput, LLMRequirementVerdict, check_requirements_llm


def _brief():
    return Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R3", type="mention_name", spec={"game_name": "Mystic Realms"}, method="llm", required=True),
            Requirement(code="R4", type="describe_game", spec={}, method="llm", required=True),
        ],
    )


def _transcript():
    return Transcript(segments=[TranscriptSegment(text="hoy traigo Mystic Realms un RPG", start=70.0, duration=3.0)])


def test_llm_parses_structured_output(mocker):
    parsed = LLMOutput(requirements=[
        LLMRequirementVerdict(requirement_code="R3", met=True, confidence=0.95,
                              evidence_quote="hoy traigo Mystic Realms", evidence_timestamp_s=70,
                              reasoning="menciona el nombre"),
        LLMRequirementVerdict(requirement_code="R4", met=True, confidence=0.88,
                              evidence_quote="un RPG", evidence_timestamp_s=72, reasoning="describe el género"),
    ])
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=parsed))]
    fake_client = mocker.Mock()
    fake_client.beta.chat.completions.parse.return_value = completion

    results = check_requirements_llm(_brief(), _transcript().full_text(), client=fake_client, model="gpt-4o-mini")

    assert {r.requirement_code for r in results} == {"R3", "R4"}
    r3 = next(r for r in results if r.requirement_code == "R3")
    assert r3.met is True and r3.confidence == 0.95
    assert r3.method == "llm"
    assert r3.evidence == "hoy traigo Mystic Realms"
    assert r3.evidence_timestamp_s == 70


def test_llm_only_includes_llm_requirements(mocker):
    parsed = LLMOutput(requirements=[
        LLMRequirementVerdict(requirement_code="R3", met=False, confidence=0.4,
                              evidence_quote=None, evidence_timestamp_s=None, reasoning="no se menciona"),
        LLMRequirementVerdict(requirement_code="R4", met=False, confidence=0.4,
                              evidence_quote=None, evidence_timestamp_s=None, reasoning="no se describe"),
    ])
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=parsed))]
    fake_client = mocker.Mock()
    fake_client.beta.chat.completions.parse.return_value = completion

    results = check_requirements_llm(_brief(), "texto sin nada", client=fake_client, model="gpt-4o-mini")
    assert all(r.method == "llm" for r in results)
    assert all(r.met is False for r in results)
