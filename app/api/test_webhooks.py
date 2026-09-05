from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.services.signature import verify_signature

MAX_AGE_SECONDS = 300

router = APIRouter(
    prefix="/test",
    tags=["Test"],
)


@router.post("/webhook/success")
async def webhook_success(payload: dict):
    return {
        "received": True,
        "payload": payload,
    }


@router.post("/webhook/error", status_code=500)
async def webhook_error():
    return {"detail": "Test error"}


# прочитать raw body;
# взять timestamp;
# пересчитать HMAC;
# сравнить через hmac.compare_digest().
@router.post("/webhook/signed")
async def webhook_signed(request: Request):
    body = await request.body()

    timestamp = request.headers.get("X-Webhook-Timestamp")
    signature = request.headers.get("X-Webhook-Signature")

    if timestamp is None or signature is None:
        raise HTTPException(
            status_code=401,
            detail="Missing signature headers",
        )

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid timestamp",
        ) from None

    now = int(datetime.now(UTC).timestamp())

    if abs(now - timestamp_int) > MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=401,
            detail="Webhook timestamp is too old",
        )

    is_valid = verify_signature(signature, settings.test_webhook_secret, timestamp, body)

    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid signature",
        )

    return {"verified": True}
