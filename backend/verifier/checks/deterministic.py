from __future__ import annotations
from verifier.models import RequirementResult


def _normalize(text: str) -> str:
    return text.lower().strip()


def check_link_in_desc(description: str, expected_link: str, code: str = "R1") -> RequirementResult:
    met = _normalize(expected_link) in _normalize(description)
    return RequirementResult(
        requirement_code=code,
        met=met,
        method="deterministic",
        evidence=expected_link if met else None,
    )


def check_code_in_desc(description: str, expected_code: str, code: str = "R2") -> RequirementResult:
    met = _normalize(expected_code) in _normalize(description)
    return RequirementResult(
        requirement_code=code,
        met=met,
        method="deterministic",
        evidence=expected_code if met else None,
    )
