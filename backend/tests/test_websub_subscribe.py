from verifier.websub.subscribe import topic_url, send_subscription


def test_topic_url():
    assert topic_url("UC123") == "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC123"


def test_send_subscribe_posts_expected_form(mocker):
    resp = mocker.Mock(status_code=202)
    post = mocker.patch("verifier.websub.subscribe.requests.post", return_value=resp)
    ok = send_subscription(
        channel_id="UC123",
        callback_url="https://app.example.com/websub/callback",
        secret="s3cr3t",
        mode="subscribe",
    )
    assert ok is True
    data = post.call_args.kwargs["data"]
    assert data["hub.mode"] == "subscribe"
    assert data["hub.topic"] == "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UC123"
    assert data["hub.callback"] == "https://app.example.com/websub/callback"
    assert data["hub.secret"] == "s3cr3t"


def test_send_subscription_returns_false_on_error(mocker):
    resp = mocker.Mock(status_code=500)
    mocker.patch("verifier.websub.subscribe.requests.post", return_value=resp)
    ok = send_subscription(channel_id="UC1", callback_url="https://x/cb", secret="s", mode="unsubscribe")
    assert ok is False
