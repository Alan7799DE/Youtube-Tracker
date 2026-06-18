from verifier.models import Brief, Requirement
from verifier.association import matching_campaigns, CandidateCampaign


def _campaign(cid, link=None, code=None):
    reqs = []
    if link:
        reqs.append(Requirement(code="R1", type="link_in_desc", spec={"expected_link": link}, method="deterministic"))
    if code:
        reqs.append(Requirement(code="R2", type="code_in_desc", spec={"code": code}, method="deterministic"))
    return CandidateCampaign(campaign_id=cid, brief=Brief(game_name="G", requirements=reqs))


def test_matches_by_link_or_code():
    desc = "Bajá el juego https://dl.game/x y usá GAMER20"
    candidates = [
        _campaign("c1", link="https://dl.game/x"),
        _campaign("c2", code="GAMER20"),
        _campaign("c3", link="https://otra.com/y"),  # no aparece
    ]
    matched = matching_campaigns(desc, candidates)
    assert set(matched) == {"c1", "c2"}


def test_no_match_returns_empty():
    matched = matching_campaigns("video sin nada", [_campaign("c1", link="https://dl.game/x")])
    assert matched == []
