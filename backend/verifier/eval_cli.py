"""Runner de evaluación de la Fase 1 contra un set dorado REAL.

Corre cada caso del set dorado de punta a punta (metadata por YouTube Data API +
transcript por youtube-transcript-api + verificación LLM por OpenAI) y reporta
cuántos veredictos coinciden con la etiqueta humana, contando aparte el peor error
posible: el **falso PASS** (el sistema dijo `pass` pero el caso NO cumple).

Uso:
    python -m verifier.eval_cli                  # usa golden/example.json
    python -m verifier.eval_cli golden/mi.json   # otro set
    python -m verifier.eval_cli --model gpt-4o   # otro modelo
    python -m verifier.eval_cli --lang en es     # idiomas de transcript

Necesita `backend/.env` con OPENAI_API_KEY y YOUTUBE_API_KEY (ver .env.example
y docs/guia-fase-1-testeo.md). No usa red en los tests: `run_eval` recibe un
runner inyectable.

Código de salida: 0 si no hubo falsos PASS ni errores; 1 en caso contrario,
para que sirva en CI / scripts.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Callable, TextIO

from pydantic import BaseModel

from verifier.models import Brief, Verification
from verifier.eval import GoldenCase, load_golden

Runner = Callable[[str, Brief], Verification]


class EvalRunResult(BaseModel):
    total: int
    correct: int
    false_pass: int  # esperado != pass pero el sistema dijo pass (el peor error)
    errors: int      # casos que tiraron excepción (sin red, sin transcript, etc.)

    @property
    def exit_code(self) -> int:
        return 0 if (self.false_pass == 0 and self.errors == 0) else 1


def build_real_runner(
    *,
    youtube_key: str,
    openai_client,
    model: str,
    languages: tuple[str, ...] = ("es", "en"),
) -> Runner:
    """Arma el runner que pega contra las APIs reales. Import perezoso para no
    requerir red ni dependencias pesadas cuando solo se testea `run_eval`."""
    from verifier.metadata import fetch_video_metadata
    from verifier.transcript import YouTubeTranscriptProvider
    from verifier.checks.llm import check_requirements_llm
    from verifier.verify import verify_video

    provider = YouTubeTranscriptProvider(languages=languages)

    def runner(video_id: str, brief: Brief) -> Verification:
        return verify_video(
            video_id,
            brief,
            metadata_client=lambda vid: fetch_video_metadata(vid, api_key=youtube_key),
            transcript_provider=provider,
            llm_check=lambda b, t: check_requirements_llm(
                b, t, client=openai_client, model=model
            ),
        )

    return runner


def run_eval(
    cases: list[GoldenCase], runner: Runner, *, out: TextIO = sys.stdout
) -> EvalRunResult:
    """Corre el runner UNA sola vez por caso (las llamadas a la API cuestan plata),
    imprime el detalle por caso y devuelve el resumen agregado."""
    correct = 0
    false_pass = 0
    errors = 0

    for case in cases:
        try:
            result = runner(case.video_id, case.brief)
        except Exception as exc:  # noqa: BLE001 - queremos seguir con los demás casos
            errors += 1
            print(f"  ERROR  {case.video_id}: {exc}", file=out)
            continue

        status = result.overall_status
        is_correct = status == case.expected_overall
        is_false_pass = status == "pass" and case.expected_overall != "pass"
        if is_correct:
            correct += 1
        if is_false_pass:
            false_pass += 1

        mark = "OK " if is_correct else "XX "
        flag = "   <-- FALSO PASS" if is_false_pass else ""
        print(
            f"  {mark} {case.video_id}: "
            f"esperado={case.expected_overall} obtenido={status}{flag}",
            file=out,
        )

    result = EvalRunResult(
        total=len(cases), correct=correct, false_pass=false_pass, errors=errors
    )
    _print_summary(result, out=out)
    return result


def _print_summary(r: EvalRunResult, *, out: TextIO) -> None:
    accuracy = (r.correct / r.total * 100) if r.total else 0.0
    print("", file=out)
    print("=" * 48, file=out)
    print(f"  Casos:      {r.total}", file=out)
    print(f"  Correctos:  {r.correct} ({accuracy:.0f}%)", file=out)
    print(f"  Falsos PASS:{r.false_pass}   <-- debe ser 0", file=out)
    print(f"  Errores:    {r.errors}", file=out)
    print("=" * 48, file=out)


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Evaluar la Fase 1 contra un set dorado real."
    )
    parser.add_argument(
        "golden",
        nargs="?",
        default="golden/example.json",
        help="Ruta al JSON del set dorado (default: golden/example.json)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        help="Modelo de OpenAI (default: LLM_MODEL del .env o gpt-4o-mini)",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        default=["es", "en"],
        help="Idiomas de transcript por orden de preferencia (default: es en)",
    )
    args = parser.parse_args(argv)

    youtube_key = os.environ.get("YOUTUBE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    missing = [
        name
        for name, val in (("YOUTUBE_API_KEY", youtube_key), ("OPENAI_API_KEY", openai_key))
        if not val
    ]
    if missing:
        print(
            "Faltan variables de entorno: "
            + ", ".join(missing)
            + ".\nCopiá backend/.env.example a backend/.env y completalas "
            "(ver docs/guia-fase-1-testeo.md).",
            file=sys.stderr,
        )
        return 2

    try:
        cases = load_golden(args.golden)
    except FileNotFoundError:
        print(f"No existe el set dorado: {args.golden}", file=sys.stderr)
        return 2

    if not cases:
        print(f"El set dorado {args.golden} está vacío.", file=sys.stderr)
        return 2

    from openai import OpenAI

    runner = build_real_runner(
        youtube_key=youtube_key,
        openai_client=OpenAI(),  # toma OPENAI_API_KEY del entorno
        model=args.model,
        languages=tuple(args.lang),
    )

    print(f"Evaluando {len(cases)} casos de {args.golden} con modelo {args.model}...\n")
    result = run_eval(cases, runner)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
