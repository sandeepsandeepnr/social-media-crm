import hmac
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.interactions import save_interaction
from app.api.tickets import route_ticket
from app.database import get_db
from app.models import Platform, PlatformCredential
from app.security import verify_webhook_signature
from config import settings

router = APIRouter()


def epoch_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        try:
            timestamp = float(value)
        except (ValueError, TypeError):
            if not isinstance(value, str):
                raise ValueError("Invalid timestamp")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        if abs(timestamp) >= 100_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook timestamp") from exc


def event_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        account_id = str(entry.get("id") or "")
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            sender = event.get("sender") or {}
            if (
                message.get("is_echo")
                or str(sender.get("id") or "") == account_id
                or not sender.get("id")
                or not (message.get("mid") or message.get("id"))
            ):
                continue
            attachments = message.get("attachments") or []
            records.append(
                {
                    "account_id": account_id,
                    "platform_interaction_id": str(
                        message.get("mid") or message.get("id")
                    ),
                    "platform_user_id": str(sender["id"]),
                    "customer_name": sender.get("name"),
                    "interaction_type": "message",
                    "content": message.get("text") or "",
                    "media_urls": [
                        item.get("payload", {}).get("url")
                        for item in attachments
                        if item.get("payload", {}).get("url")
                    ],
                    "is_public": False,
                    "captured_at": epoch_datetime(event.get("timestamp")),
                    "platform_metadata": {"webhook_event": "messaging"},
                }
            )
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            sender = value.get("from") or value.get("sender") or {}
            field = change.get("field", "")
            if field not in {"feed", "comments", "mention"}:
                continue
            if field == "feed" and (
                value.get("item") not in {None, "comment"}
                or value.get("verb") not in {None, "add"}
            ):
                continue
            if str(sender.get("id") or "") == account_id:
                continue
            interaction_id = value.get("comment_id") or value.get("id")
            if not interaction_id or not sender.get("id"):
                continue
            interaction_type = "mention" if field == "mention" else "comment"
            records.append(
                {
                    "account_id": account_id,
                    "platform_interaction_id": str(interaction_id),
                    "platform_user_id": str(sender["id"]),
                    "customer_name": sender.get("name"),
                    "interaction_type": interaction_type,
                    "content": value.get("text") or value.get("message") or "",
                    "media_urls": [],
                    "post_url": value.get("permalink_url"),
                    "is_public": True,
                    "captured_at": epoch_datetime(value.get("created_time")),
                    "platform_metadata": {
                        "webhook_event": field or "changes",
                        "post_id": value.get("post_id"),
                        "parent_id": str(value["parent_id"]) if value.get("parent_id") else None,
                    },
                }
            )
    return records


@router.get("/social-media/{platform}")
def verify_webhook(
    platform: str,
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if platform.lower() not in {"facebook", "instagram"}:
        raise HTTPException(status_code=404, detail="Webhook platform is not supported")
    if (
        mode == "subscribe"
        and verify_token
        and challenge
        and hmac.compare_digest(verify_token, settings.WEBHOOK_VERIFY_TOKEN)
    ):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/social-media/{platform}")
async def receive_webhook(
    platform: str,
    request: Request,
    db: Session = Depends(get_db),
    signature: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    platform_name = platform.lower()
    if platform_name not in {"facebook", "instagram"}:
        raise HTTPException(status_code=404, detail="Webhook platform is not supported")
    body = await request.body()
    if not verify_webhook_signature(body, signature, settings.FACEBOOK_APP_SECRET):
        raise HTTPException(
            status_code=401, detail="Webhook signature is invalid or missing"
        )
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Webhook payload must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Webhook payload must be a JSON object"
        )
    platform_row = db.query(Platform).filter_by(name=platform_name).one_or_none()
    if platform_row is None:
        raise HTTPException(status_code=404, detail="Platform is not configured")
    records = event_records(payload)
    captured = 0
    for record in records:
        if not record["account_id"]:
            raise HTTPException(status_code=400, detail="Webhook account ID is missing")
        query = db.query(PlatformCredential).filter_by(
            platform_id=platform_row.id,
            is_active=True,
            business_account_id=record["account_id"],
        )
        credential = query.first()
        if credential is None:
            raise HTTPException(
                status_code=503,
                detail=f"No active {platform_name} account matches webhook account '{record['account_id']}'",
            )
        record["platform"] = platform_name
        record["business_account_id"] = record["account_id"]
        record["webhook_verified"] = bool(settings.FACEBOOK_APP_SECRET)
        interaction = save_interaction(db, record)
        if interaction.created_at is None:
            db.flush()
        route_ticket(db, interaction, credential)
        captured += 1
        credential.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"status": "received", "captured": captured}
