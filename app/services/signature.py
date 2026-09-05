import hashlib
import hmac


def build_signed_message(timestamp: str, body: bytes) -> bytes:
    return timestamp.encode() + b"." + body


def generate_signature(
    secret: str,
    timestamp: str,
    body: bytes,
):
    return hmac.new(
        secret.encode(), build_signed_message(timestamp, body), hashlib.sha256
    ).hexdigest()


def verify_signature(
    signature: str,
    secret: str,
    timestamp: str,
    body: bytes,
) -> bool:
    expected_signature = generate_signature(secret, timestamp, body)
    return hmac.compare_digest(expected_signature, signature)
