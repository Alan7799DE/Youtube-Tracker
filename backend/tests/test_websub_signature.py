import hashlib
import hmac
from verifier.websub.signature import is_valid_signature


def test_valid_signature():
    body = b"<feed/>"
    secret = "s3cr3t"
    digest = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    assert is_valid_signature(body, f"sha1={digest}", secret) is True


def test_invalid_signature():
    assert is_valid_signature(b"<feed/>", "sha1=deadbeef", "s3cr3t") is False


def test_missing_header():
    assert is_valid_signature(b"<feed/>", None, "s3cr3t") is False
