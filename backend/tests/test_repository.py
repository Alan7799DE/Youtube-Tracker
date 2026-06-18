from verifier.models import Verification, RequirementResult
from verifier.repository import save_verification


def test_save_inserts_verification_and_results(mocker):
    client = mocker.Mock()
    table = mocker.Mock()
    client.table.return_value = table
    table.insert.return_value = table
    table.execute.return_value = mocker.Mock(data=[{"id": "ver-1"}])

    v = Verification(
        overall_status="pass",
        results=[RequirementResult(requirement_code="R1", met=True, method="deterministic")],
        model="gpt-4o-mini",
    )
    ver_id = save_verification(
        client, org_id="org-1", video_id="vid-1", campaign_id="camp-1",
        requirement_ids={"R1": "req-1"}, verification=v,
    )
    assert ver_id == "ver-1"
    assert client.table.call_count >= 2  # verifications + requirement_results
