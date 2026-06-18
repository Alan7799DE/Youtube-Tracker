"""Casos borde adicionales para el núcleo de verificación (Fase 1).

Complementan los tests por módulo. Cada bloque apunta a un comportamiento
claramente correcto del diseño (boundaries de confianza, requisitos opcionales,
payloads parciales, transcript vacío, etc.). No congelan comportamiento dudoso.
"""
from __future__ import annotations

import requests

import pytest

from verifier.models import (
    Brief, Requirement, VideoMetadata, Transcript, TranscriptSegment,
    RequirementResult, Verification,
)
from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc
from verifier.decision import decide
from verifier.verify import verify_video, evaluate_brief
from verifier.metadata import fetch_video_metadata
from verifier.transcript import YouTubeTranscriptProvider
from verifier.checks.llm import LLMOutput, LLMRequirementVerdict, check_requirements_llm
from verifier.eval import evaluate, load_golden, GoldenCase


# --------------------------------------------------------------------------
# Requirement helpers
# --------------------------------------------------------------------------
LINK_REQ = Requirement(code="R1", type="link_in_desc", spec={}, method="deterministic", required=True)
LINK_OPT = Requirement(code="R1", type="link_in_desc", spec={}, method="deterministic", required=False)
CODE_REQ = Requirement(code="R2", type="code_in_desc", spec={}, method="deterministic", required=True)
GAME_REQ = Requirement(code="R3", type="mention_name", spec={}, method="llm", required=True)
GAME_OPT = Requirement(code="R3", type="mention_name", spec={}, method="llm", required=False)
PLAY_REQ = Requirement(code="R5", type="show_gameplay", spec={}, method="human", required=True)


# --------------------------------------------------------------------------
# deterministic.py
# --------------------------------------------------------------------------
def test_whitespace_only_expected_link_is_not_met():
    # Un expected_link con solo espacios se normaliza a "" -> NO debe dar PASS.
    r = check_link_in_desc("Bajá: https://dl.game/x", "   ")
    assert r.met is False
    assert r.evidence is None


def test_empty_description_with_expected_is_not_met():
    r = check_code_in_desc("", "gamer20")
    assert r.met is False


def test_surrounding_whitespace_in_expected_is_tolerated():
    # Espacios alrededor del valor esperado no deben impedir el match (se normaliza).
    r = check_code_in_desc("usá el código GAMER20 ya", "  gamer20  ")
    assert r.met is True


def test_link_match_is_case_insensitive_in_both_sides():
    r = check_link_in_desc("MIRA AQUI HTTPS://DL.GAME/X GRACIAS", "https://dl.game/x")
    assert r.met is True


# --------------------------------------------------------------------------
# decision.py
# --------------------------------------------------------------------------
def test_confidence_exactly_at_threshold_is_not_review():
    # El umbral es estricto (< 0.8); confidence == 0.8 NO cae a review.
    results = [RequirementResult(requirement_code="R3", met=True, confidence=0.8, method="llm")]
    assert decide(results, [GAME_REQ]) == "pass"


def test_confidence_just_below_threshold_is_review():
    results = [RequirementResult(requirement_code="R3", met=True, confidence=0.79, method="llm")]
    assert decide(results, [GAME_REQ]) == "review"


def test_no_requirements_no_results_is_pass():
    assert decide([], []) == "pass"


def test_optional_deterministic_not_met_does_not_fail():
    # Un requisito determinístico OPCIONAL que no se cumple no bloquea el PASS.
    results = [RequirementResult(requirement_code="R1", met=False, method="deterministic")]
    assert decide(results, [LINK_OPT]) == "pass"


def test_optional_llm_not_met_high_confidence_does_not_fail():
    # Requisito LLM OPCIONAL no cumplido con confianza alta no fuerza FAIL.
    results = [RequirementResult(requirement_code="R3", met=False, confidence=0.95, method="llm")]
    assert decide(results, [GAME_OPT]) == "pass"


def test_deterministic_fail_takes_precedence_over_low_confidence_llm():
    # Regla 1 (det requerido falla -> FAIL) gana sobre la regla 2 (LLM dudoso -> REVIEW).
    results = [
        RequirementResult(requirement_code="R1", met=False, method="deterministic"),
        RequirementResult(requirement_code="R3", met=True, confidence=0.5, method="llm"),
    ]
    assert decide(results, [LINK_REQ, GAME_REQ]) == "fail"


def test_one_of_several_deterministic_required_failing_is_fail():
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R2", met=False, method="deterministic"),
    ]
    assert decide(results, [LINK_REQ, CODE_REQ]) == "fail"


def test_resolved_human_requirement_is_not_pending():
    # Un requisito humano CON resultado (cumplido) ya no está pendiente -> no fuerza REVIEW.
    results = [
        RequirementResult(requirement_code="R1", met=True, method="deterministic"),
        RequirementResult(requirement_code="R5", met=True, method="human"),
    ]
    assert decide(results, [LINK_REQ, PLAY_REQ]) == "pass"


# --------------------------------------------------------------------------
# verify.py
# --------------------------------------------------------------------------
def _det_only_brief():
    return Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R1", type="link_in_desc", spec={"expected_link": "https://dl.game/x"}, method="deterministic", required=True),
            Requirement(code="R2", type="code_in_desc", spec={"code": "GAMER20"}, method="deterministic", required=True),
        ],
    )


def test_deterministic_only_brief_skips_transcript_and_llm(mocker):
    md = VideoMetadata(video_id="v", description="https://dl.game/x GAMER20")
    metadata_client = mocker.Mock(return_value=md)
    provider = mocker.Mock()
    llm = mocker.Mock()

    v = verify_video("v", _det_only_brief(), metadata_client=metadata_client,
                     transcript_provider=provider, llm_check=llm)
    assert v.overall_status == "pass"
    provider.get_transcript.assert_not_called()  # sin requisitos LLM no baja transcript
    llm.assert_not_called()


def test_deterministic_required_fail_yields_fail_overall(mocker):
    brief = Brief(
        game_name="Mystic Realms",
        requirements=[
            Requirement(code="R1", type="link_in_desc", spec={"expected_link": "https://dl.game/x"}, method="deterministic", required=True),
            Requirement(code="R3", type="mention_name", spec={"game_name": "Mystic Realms"}, method="llm", required=True),
        ],
    )
    md = VideoMetadata(video_id="v", description="sin el link esperado")  # R1 no se cumple
    metadata_client = mocker.Mock(return_value=md)
    provider = mocker.Mock()
    provider.get_transcript.return_value = Transcript(segments=[TranscriptSegment(text="hola", start=0.0, duration=1.0)])
    llm = mocker.Mock(return_value=[RequirementResult(requirement_code="R3", met=True, confidence=0.95, method="llm")])

    v = verify_video("v", brief, metadata_client=metadata_client,
                     transcript_provider=provider, llm_check=llm)
    assert v.overall_status == "fail"


def test_evaluate_brief_reuses_provided_transcript_without_fetch(mocker):
    # Camino reutilizable para Fase 3: evaluate_brief NO hace fetch.
    brief = _det_only_brief()
    md = VideoMetadata(video_id="v", description="https://dl.game/x GAMER20")
    llm = mocker.Mock()
    v = evaluate_brief(brief, md, transcript=None, llm_check=llm)
    assert v.overall_status == "pass"
    llm.assert_not_called()


# --------------------------------------------------------------------------
# metadata.py
# --------------------------------------------------------------------------
def test_metadata_partial_payload_uses_defaults(mocker):
    payload = {"items": [{"snippet": {"title": "Solo título"}}]}  # sin contentDetails ni demás campos
    resp = mocker.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    mocker.patch("verifier.metadata.requests.get", return_value=resp)

    md = fetch_video_metadata("vid123", api_key="KEY")
    assert md.title == "Solo título"
    assert md.description == ""
    assert md.channel_id == ""
    assert md.published_at is None
    assert md.duration is None


def test_metadata_http_error_propagates(mocker):
    resp = mocker.Mock()
    resp.raise_for_status.side_effect = requests.HTTPError("500")
    mocker.patch("verifier.metadata.requests.get", return_value=resp)
    with pytest.raises(requests.HTTPError):
        fetch_video_metadata("vid123", api_key="KEY")


# --------------------------------------------------------------------------
# transcript.py
# --------------------------------------------------------------------------
def test_transcript_provider_handles_empty_segments(mocker):
    mocker.patch("verifier.transcript.YouTubeTranscriptApi.fetch", return_value=[])
    t = YouTubeTranscriptProvider().get_transcript("vid123")
    assert isinstance(t, Transcript)
    assert t.segments == []
    assert t.full_text() == ""


# --------------------------------------------------------------------------
# checks/llm.py
# --------------------------------------------------------------------------
def _llm_brief():
    return Brief(
        game_name="Mystic Realms",
        requirements=[Requirement(code="R3", type="mention_name", spec={}, method="llm", required=True)],
    )


def test_llm_empty_output_returns_empty_list(mocker):
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=LLMOutput(requirements=[])))]
    client = mocker.Mock()
    client.beta.chat.completions.parse.return_value = completion
    assert check_requirements_llm(_llm_brief(), "texto", client=client, model="m") == []


def test_llm_maps_none_evidence_fields(mocker):
    parsed = LLMOutput(requirements=[
        LLMRequirementVerdict(requirement_code="R3", met=True, confidence=0.9,
                              evidence_quote=None, evidence_timestamp_s=None, reasoning=None),
    ])
    completion = mocker.Mock()
    completion.choices = [mocker.Mock(message=mocker.Mock(parsed=parsed))]
    client = mocker.Mock()
    client.beta.chat.completions.parse.return_value = completion

    [r] = check_requirements_llm(_llm_brief(), "texto", client=client, model="m")
    assert r.met is True
    assert r.evidence is None
    assert r.evidence_timestamp_s is None
    assert r.method == "llm"


# --------------------------------------------------------------------------
# eval.py
# --------------------------------------------------------------------------
def test_evaluate_empty_cases():
    report = evaluate([], runner=lambda vid, brief: Verification(overall_status="pass", results=[]))
    assert report.total == 0
    assert report.correct == 0
    assert report.false_pass == 0


def test_evaluate_review_correct_and_false_pass_counts():
    cases = [
        GoldenCase(video_id="r", expected_overall="review", brief=Brief(game_name="G", requirements=[])),
        GoldenCase(video_id="f", expected_overall="fail", brief=Brief(game_name="G", requirements=[])),
    ]

    def runner(video_id, brief):
        if video_id == "r":
            return Verification(overall_status="review", results=[])  # correcto
        return Verification(overall_status="pass", results=[])  # falso PASS (esperaba fail)

    report = evaluate(cases, runner=runner)
    assert report.total == 2
    assert report.correct == 1     # solo el review
    assert report.false_pass == 1  # el fail que salió pass


def test_load_golden_reads_file(tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(
        '[{"video_id": "abc", "expected_overall": "pass", '
        '"brief": {"game_name": "Mystic Realms", "requirements": '
        '[{"code": "R1", "type": "link_in_desc", "spec": {"expected_link": "https://dl.game/x"}, '
        '"method": "deterministic", "required": true}]}}]',
        encoding="utf-8",
    )
    cases = load_golden(str(path))
    assert len(cases) == 1
    assert cases[0].video_id == "abc"
    assert cases[0].expected_overall == "pass"
    assert cases[0].brief.game_name == "Mystic Realms"
    assert cases[0].brief.requirements[0].code == "R1"


# --------------------------------------------------------------------------
# models.py
# --------------------------------------------------------------------------
def test_full_text_empty_segments_is_empty_string():
    assert Transcript(segments=[]).full_text() == ""


def test_full_text_strips_outer_whitespace():
    t = Transcript(segments=[
        TranscriptSegment(text="  hola", start=0.0, duration=1.0),
        TranscriptSegment(text="mundo  ", start=1.0, duration=1.0),
    ])
    assert t.full_text() == "hola mundo"
