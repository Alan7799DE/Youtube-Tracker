from verifier.channel_status import next_channel_status


def test_pass_sets_verified():
    assert next_channel_status("pending", "pass") == "verified"


def test_fail_sets_incomplete():
    assert next_channel_status("pending", "fail") == "incomplete"


def test_review_keeps_current():
    assert next_channel_status("pending", "review") == "pending"
    assert next_channel_status("incomplete", "review") == "incomplete"


def test_verified_never_regresses():
    assert next_channel_status("verified", "fail") == "verified"
    assert next_channel_status("verified", "review") == "verified"


def test_incomplete_can_upgrade_to_verified():
    assert next_channel_status("incomplete", "pass") == "verified"
