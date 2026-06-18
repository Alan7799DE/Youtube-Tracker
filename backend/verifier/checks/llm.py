from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from verifier.models import Brief, RequirementResult


class LLMRequirementVerdict(BaseModel):
    requirement_code: str
    met: bool
    confidence: float
    evidence_quote: Optional[str] = None
    evidence_timestamp_s: Optional[int] = None
    reasoning: Optional[str] = None


class LLMOutput(BaseModel):
    requirements: list[LLMRequirementVerdict]


SYSTEM_PROMPT = (
    "Sos un verificador de cumplimiento publicitario. Recibís el brief de una campaña "
    "y el transcript de un video. Para cada requisito pedido, decidí si se cumple, con una "
    "confianza de 0 a 1 y una cita textual como evidencia. El nombre del juego puede estar "
    "mal transcripto (errores fonéticos, inglés/japonés): detectá si ESE juego se menciona "
    "tolerando esos errores. Ante la duda, baja la confianza; no inventes evidencia."
)


def _build_user_prompt(brief: Brief, transcript_text: str) -> str:
    llm_reqs = [r for r in brief.requirements if r.method == "llm"]
    lines = [f"Juego (nombre canónico): {brief.game_name}", "", "Requisitos LLM a verificar:"]
    for r in llm_reqs:
        lines.append(f"- {r.code} ({r.type}): {r.spec}")
    lines += ["", "Transcript:", transcript_text]
    return "\n".join(lines)


def check_requirements_llm(
    brief: Brief, transcript_text: str, *, client, model: str = "gpt-4o-mini"
) -> list[RequirementResult]:
    # NOTE: client.beta.chat.completions.parse should be confirmed against the installed openai SDK for real runtime.
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(brief, transcript_text)},
        ],
        response_format=LLMOutput,
    )
    parsed: LLMOutput = completion.choices[0].message.parsed
    return [
        RequirementResult(
            requirement_code=v.requirement_code,
            met=v.met,
            confidence=v.confidence,
            method="llm",
            evidence=v.evidence_quote,
            evidence_timestamp_s=v.evidence_timestamp_s,
            reasoning=v.reasoning,
        )
        for v in parsed.requirements
    ]
