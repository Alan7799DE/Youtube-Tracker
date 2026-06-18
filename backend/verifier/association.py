from __future__ import annotations
from pydantic import BaseModel
from verifier.models import Brief
from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc


class CandidateCampaign(BaseModel):
    campaign_id: str
    brief: Brief


def _is_ad_for(description: str, brief: Brief) -> bool:
    for req in brief.requirements:
        if req.type == "link_in_desc":
            if check_link_in_desc(description, req.spec.get("expected_link", "")).met:
                return True
        elif req.type == "code_in_desc":
            if check_code_in_desc(description, req.spec.get("code", "")).met:
                return True
    return False


def matching_campaigns(description: str, candidates: list[CandidateCampaign]) -> list[str]:
    return [c.campaign_id for c in candidates if _is_ad_for(description, c.brief)]
