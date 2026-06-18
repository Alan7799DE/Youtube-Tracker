"""Persistencia de verificaciones en Supabase.

Para uso real:
  1. pip install supabase
  2. from supabase import create_client
     client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)
     # SERVICE_ROLE_KEY bypasses RLS
  3. Haber ejecutado schema.sql contra tu proyecto Supabase.

El cliente se inyecta desde fuera, por lo que en tests se usa un mock;
la verificación contra la DB real es un paso manual fuera de scope aquí.
"""
from __future__ import annotations

from verifier.models import Verification


def save_verification(
    client,
    *,
    org_id: str,
    video_id: str,
    campaign_id: str,
    requirement_ids: dict[str, str],
    verification: Verification,
) -> str:
    """Inserta la verificación y sus resultados.

    `client` es un cliente Supabase con service_role (bypassea RLS).
    `requirement_ids` mapea requirement_code -> requirements.id.

    Devuelve el UUID de la fila insertada en `verifications`.
    """
    ver_row = (
        client.table("verifications")
        .insert({
            "org_id": org_id,
            "video_id": video_id,
            "campaign_id": campaign_id,
            "overall_status": verification.overall_status,
            "model": verification.model,
            "raw_output": verification.raw_output,
        })
        .execute()
    )
    verification_id = ver_row.data[0]["id"]

    rows = [
        {
            "org_id": org_id,
            "verification_id": verification_id,
            "requirement_id": requirement_ids[r.requirement_code],
            "met": r.met,
            "confidence": r.confidence,
            "method": r.method,
            "evidence": r.evidence,
            "evidence_timestamp_s": r.evidence_timestamp_s,
        }
        for r in verification.results
        if r.requirement_code in requirement_ids
    ]
    if rows:
        client.table("requirement_results").insert(rows).execute()

    return verification_id
