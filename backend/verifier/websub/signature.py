from __future__ import annotations
import hashlib
import hmac
from typing import Optional


def is_valid_signature(body: bytes, header: Optional[str], secret: str) -> bool:
    if not header or "=" not in header:
        return False
    algo, _, received = header.partition("=")
    algos = {"sha1": hashlib.sha1, "sha256": hashlib.sha256}
    if algo not in algos:
        return False
    expected = hmac.new(secret.encode(), body, algos[algo]).hexdigest()
    return hmac.compare_digest(expected, received)
