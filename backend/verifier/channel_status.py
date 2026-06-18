from __future__ import annotations
from verifier.models import OverallStatus

ChannelStatus = str  # 'pending' | 'verified' | 'incomplete' | 'failed'


def next_channel_status(current: ChannelStatus, verdict: OverallStatus) -> ChannelStatus:
    """Aplica una verificación al estado del campaign_channel.
    Precedencia: verified > incomplete > pending. 'failed' lo decide el revisor de plazos."""
    if current == "verified":
        return "verified"  # estado ganador, no retrocede
    if verdict == "pass":
        return "verified"
    if verdict == "fail":
        return "incomplete"
    # verdict == "review": no cambia (sigue esperando / cola humana)
    return current
