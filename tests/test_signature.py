import json
from datetime import UTC, datetime

from app.api.test_webhooks import MAX_AGE_SECONDS
from app.core.config import settings
from app.services.signature import generate_signature


def make_body(payload: dict) -> bytes:
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def make_headers(
    secret: str,
    timestamp: str,
    body: bytes,
) -> dict[str, str]:
    signature = generate_signature(
        secret,
        timestamp,
        body,
    )

    return {
        "Content-Type": "application/json",
        "X-Webhook-Id": "test-event-id",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": signature,
    }


def current_timestamp() -> str:
    return str(int(datetime.now(UTC).timestamp()))


def test_valid_signature_is_accepted(client):
    body = make_body(
        {
            "event": "payment.completed",
            "amount": 1000,
        }
    )
    timestamp = current_timestamp()

    headers = make_headers(
        settings.test_webhook_secret,
        timestamp,
        body,
    )

    response = client.post(
        "/test/webhook/signed",
        content=body,
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "verified": True,
    }


def test_modified_payload_is_rejected(client):
    original_body = make_body(
        {
            "amount": 1000,
        }
    )
    modified_body = make_body(
        {
            "amount": 9999,
        }
    )
    timestamp = current_timestamp()

    # Подпись рассчитана для исходного payload.
    headers = make_headers(
        settings.test_webhook_secret,
        timestamp,
        original_body,
    )

    # Отправляется уже изменённый payload.
    response = client.post(
        "/test/webhook/signed",
        content=modified_body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid signature",
    }


def test_wrong_secret_is_rejected(client):
    body = make_body(
        {
            "event": "payment.completed",
        }
    )
    timestamp = current_timestamp()

    headers = make_headers(
        "whsec_wrong_secret",
        timestamp,
        body,
    )

    response = client.post(
        "/test/webhook/signed",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid signature",
    }


def test_modified_timestamp_is_rejected(client):
    body = make_body(
        {
            "event": "payment.completed",
        }
    )

    signed_timestamp = current_timestamp()

    headers = make_headers(
        settings.test_webhook_secret,
        signed_timestamp,
        body,
    )

    # Меняем timestamp после расчёта подписи.
    headers["X-Webhook-Timestamp"] = str(int(signed_timestamp) + 1)

    response = client.post(
        "/test/webhook/signed",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid signature",
    }


def test_old_timestamp_is_rejected(client):
    body = make_body(
        {
            "event": "payment.completed",
        }
    )

    old_timestamp = str(int(datetime.now(UTC).timestamp()) - MAX_AGE_SECONDS - 1)

    # Подпись корректна для этого timestamp,
    # но сам timestamp уже слишком старый.
    headers = make_headers(
        settings.test_webhook_secret,
        old_timestamp,
        body,
    )

    response = client.post(
        "/test/webhook/signed",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Webhook timestamp is too old",
    }


def test_same_input_produces_same_signature():
    body = make_body(
        {
            "event": "payment.completed",
            "amount": 1000,
        }
    )
    secret = "whsec_same_secret"
    timestamp = "1788500000"

    first_signature = generate_signature(
        secret,
        timestamp,
        body,
    )
    second_signature = generate_signature(
        secret,
        timestamp,
        body,
    )

    assert first_signature == second_signature


def test_different_secret_produces_different_signature():
    body = make_body(
        {
            "event": "payment.completed",
            "amount": 1000,
        }
    )
    timestamp = "1788500000"

    first_signature = generate_signature(
        "whsec_first",
        timestamp,
        body,
    )
    second_signature = generate_signature(
        "whsec_second",
        timestamp,
        body,
    )

    assert first_signature != second_signature
