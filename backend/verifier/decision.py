from __future__ import annotations
from verifier.models import Requirement, RequirementResult, OverallStatus

CONFIDENCE_THRESHOLD = 0.8


def decide(results: list[RequirementResult], requirements: list[Requirement]) -> OverallStatus:
    by_code = {r.code: r for r in requirements}
    res_by_code = {r.requirement_code: r for r in results}

    # 0. El veredicto humano manda: si un requisito humano REQUERIDO fue revisado
    #    y NO cumple, el resultado es FAIL con prioridad sobre todas las demás reglas.
    for r in results:
        req = by_code.get(r.requirement_code)
        if req and req.required and r.method == "human" and not r.met:
            return "fail"

    # 1. Si algún requisito determinístico REQUERIDO falló -> FAIL
    for r in results:
        req = by_code.get(r.requirement_code)
        if req and req.required and r.method == "deterministic" and not r.met:
            return "fail"

    # 2. Si algún requisito LLM tiene confidence < umbral -> REVIEW (ante la duda, primero)
    for r in results:
        if r.method == "llm" and (r.confidence is None or r.confidence < CONFIDENCE_THRESHOLD):
            return "review"

    # 3. Si algún requisito LLM REQUERIDO no se cumple con confianza alta -> FAIL
    for r in results:
        req = by_code.get(r.requirement_code)
        if req and req.required and r.method == "llm" and not r.met:
            return "fail"

    # 4. Si hay requisitos visuales/humanos pendientes (sin resultado automático) -> REVIEW
    pending_visual = [
        req for req in requirements
        if req.method == "human" and req.code not in res_by_code
    ]
    if pending_visual:
        return "review"

    # 5. Todo cumple, sin pendientes -> PASS
    return "pass"
