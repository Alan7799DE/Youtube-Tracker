from __future__ import annotations
import argparse
import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI
from verifier.models import Brief
from verifier.metadata import fetch_video_metadata
from verifier.transcript import YouTubeTranscriptProvider
from verifier.checks.llm import check_requirements_llm
from verifier.verify import verify_video


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Verificar un video contra un brief (Fase 1)")
    parser.add_argument("video_id", help="ID del video de YouTube")
    parser.add_argument("brief", help="Ruta a un JSON con el brief")
    args = parser.parse_args(argv)

    youtube_key = os.environ["YOUTUBE_API_KEY"]
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    openai_client = OpenAI()  # toma OPENAI_API_KEY del entorno

    brief = Brief.model_validate_json(open(args.brief, encoding="utf-8").read())

    verification = verify_video(
        args.video_id,
        brief,
        metadata_client=lambda vid: fetch_video_metadata(vid, api_key=youtube_key),
        transcript_provider=YouTubeTranscriptProvider(),
        llm_check=lambda b, t: check_requirements_llm(b, t, client=openai_client, model=model),
    )
    print(verification.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
