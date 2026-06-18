from __future__ import annotations
from typing import Literal
import requests

HUB_URL = "https://pubsubhubbub.appspot.com/subscribe"
TOPIC_TEMPLATE = "https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"


def topic_url(channel_id: str) -> str:
    return TOPIC_TEMPLATE.format(channel_id=channel_id)


def send_subscription(
    *, channel_id: str, callback_url: str, secret: str,
    mode: Literal["subscribe", "unsubscribe"],
) -> bool:
    data = {
        "hub.mode": mode,
        "hub.topic": topic_url(channel_id),
        "hub.callback": callback_url,
        "hub.secret": secret,
        "hub.verify": "async",
    }
    resp = requests.post(HUB_URL, data=data, timeout=15)
    return resp.status_code in (202, 204)
