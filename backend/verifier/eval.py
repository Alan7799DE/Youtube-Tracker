from __future__ import annotations
import json
from typing import Callable
from pydantic import BaseModel
from verifier.models import Brief, Verification, OverallStatus


class GoldenCase(BaseModel):
    video_id: str
    expected_overall: OverallStatus
    brief: Brief


class EvalReport(BaseModel):
    total: int
    correct: int
    false_pass: int  # esperado != pass pero el sistema dijo pass (el peor error)


Runner = Callable[[str, Brief], Verification]


def load_golden(path: str) -> list[GoldenCase]:
    data = json.loads(open(path, encoding="utf-8").read())
    return [GoldenCase.model_validate(c) for c in data]


def evaluate(cases: list[GoldenCase], runner: Runner) -> EvalReport:
    correct = 0
    false_pass = 0
    for case in cases:
        result = runner(case.video_id, case.brief)
        if result.overall_status == case.expected_overall:
            correct += 1
        if result.overall_status == "pass" and case.expected_overall != "pass":
            false_pass += 1
    return EvalReport(total=len(cases), correct=correct, false_pass=false_pass)
