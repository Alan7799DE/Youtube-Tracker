from verifier.channels.refs import parse_channel_ref, ChannelRef


def test_channel_id_url():
    r = parse_channel_ref("https://www.youtube.com/channel/UC123abc")
    assert r == ChannelRef(kind="channel_id", value="UC123abc")


def test_handle_url():
    r = parse_channel_ref("https://youtube.com/@GamerPro")
    assert r == ChannelRef(kind="handle", value="GamerPro")


def test_bare_handle():
    assert parse_channel_ref("@GamerPro") == ChannelRef(kind="handle", value="GamerPro")


def test_bare_channel_id():
    assert parse_channel_ref("UC123abc") == ChannelRef(kind="channel_id", value="UC123abc")


def test_legacy_user_url():
    assert parse_channel_ref("https://youtube.com/user/OldName") == ChannelRef(kind="username", value="OldName")


def test_unknown_is_unknown():
    assert parse_channel_ref("Gamer Pro").kind == "unknown"
