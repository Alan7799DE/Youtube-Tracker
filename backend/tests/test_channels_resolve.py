from verifier.channels.refs import ChannelRef
from verifier.channels.resolve import resolve_channel, ResolvedChannel


def _resp(mocker, payload):
    resp = mocker.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_resolve_by_handle(mocker):
    payload = {"items": [{"id": "UC999", "snippet": {"title": "GamerPro", "customUrl": "@gamerpro"}}]}
    get = mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="handle", value="gamerpro"), api_key="K")
    assert r == ResolvedChannel(channel_id="UC999", name="GamerPro", handle="@gamerpro")
    assert get.call_args.kwargs["params"]["forHandle"] == "@gamerpro"


def test_resolve_channel_id_passthrough(mocker):
    payload = {"items": [{"id": "UC123", "snippet": {"title": "Canal", "customUrl": "@canal"}}]}
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, payload))
    r = resolve_channel(ChannelRef(kind="channel_id", value="UC123"), api_key="K")
    assert r.channel_id == "UC123"


def test_resolve_not_found_returns_none(mocker):
    mocker.patch("verifier.channels.resolve.requests.get", return_value=_resp(mocker, {"items": []}))
    r = resolve_channel(ChannelRef(kind="handle", value="nope"), api_key="K")
    assert r is None


def test_resolve_unknown_kind_returns_none(mocker):
    get = mocker.patch("verifier.channels.resolve.requests.get")
    r = resolve_channel(ChannelRef(kind="unknown", value="Gamer Pro"), api_key="K")
    assert r is None
    get.assert_not_called()
