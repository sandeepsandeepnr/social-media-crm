from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Interaction,
    PlatformCredential,
    Response,
    Ticket,
    TicketInteraction,
    User,
)
from app.schemas import ResponseCreate, ResponseUpdate
from app.security import decrypt_secret, get_current_user
from app.utils import create_audit
from config import settings

router = APIRouter()


def response_data(row: Response) -> dict:
    return {
        "id": str(row.id),
        "ticket_id": str(row.ticket_id),
        "content": row.content,
        "status": row.status,
        "platform": row.platform.name,
        "character_count": len(row.content),
        "max_characters": row.platform.max_message_length,
        "agent": row.agent.username,
        "created_at": row.created_at,
        "sent_at": row.sent_at,
        "error_message": row.error_message,
    }


def can_access_ticket(ticket: Ticket, user: User) -> bool:
    return user.role != "agent" or ticket.assigned_to_agent_id in {None, user.id}


@router.post("", status_code=201)
def create_response(
    payload: ResponseCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, payload.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not can_access_ticket(ticket, user):
        raise HTTPException(
            status_code=403, detail="Ticket is assigned to another agent"
        )
    interaction_id = (
        payload.responding_to_interaction_id or ticket.primary_interaction_id
    )
    interaction = db.get(Interaction, interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    linked = (
        db.query(TicketInteraction)
        .filter_by(ticket_id=ticket.id, interaction_id=interaction.id)
        .first()
    )
    if linked is None:
        raise HTTPException(
            status_code=400, detail="Response target must be linked to the ticket"
        )
    platform = interaction.platform
    if (
        platform.max_message_length
        and len(payload.content) > platform.max_message_length
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Response exceeds {platform.max_message_length} characters for {platform.display_name}",
        )
    row = Response(
        ticket_id=ticket.id,
        platform_id=platform.id,
        agent_id=user.id,
        responding_to_interaction_id=interaction.id,
        content=payload.content,
        response_type="manual",
        status="draft",
        is_private_message=payload.is_private_message,
    )
    db.add(row)
    create_audit(db, request, user, "response.drafted", "response", row.id)
    db.commit()
    db.refresh(row)
    return response_data(row)


@router.get("/{response_id}")
def get_response(
    response_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Response, response_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Response not found")
    ticket = db.get(Ticket, row.ticket_id)
    if ticket is None or not can_access_ticket(ticket, user):
        raise HTTPException(
            status_code=403, detail="Response is not accessible to this user"
        )
    return response_data(row)


@router.put("/{response_id}")
def update_response(
    response_id: UUID,
    payload: ResponseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Response, response_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Response not found")
    if row.agent_id != user.id and user.role not in {"admin", "team_leader"}:
        raise HTTPException(
            status_code=403,
            detail="Only the author or a supervisor may edit this response",
        )
    if row.status not in {"draft", "failed"}:
        raise HTTPException(
            status_code=409, detail="Only draft or failed responses can be edited"
        )
    if (
        row.platform.max_message_length
        and len(payload.content) > row.platform.max_message_length
    ):
        raise HTTPException(
            status_code=422, detail="Response exceeds the platform character limit"
        )
    old_content = row.content
    row.content = payload.content
    row.status = "draft"
    row.error_message = None
    create_audit(
        db,
        request,
        user,
        "response.updated",
        "response",
        row.id,
        old_values={"content": old_content},
        new_values={"content": row.content},
    )
    db.commit()
    db.refresh(row)
    return response_data(row)


@router.post("/{response_id}/send")
async def send_response(
    response_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(Response, response_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Response not found")
    ticket = db.get(Ticket, row.ticket_id)
    if ticket is None or not can_access_ticket(ticket, user):
        raise HTTPException(
            status_code=403, detail="Ticket is not accessible to this user"
        )
    if row.agent_id != user.id and user.role not in {"admin", "team_leader"}:
        raise HTTPException(
            status_code=403,
            detail="Only the author or a supervisor may send this response",
        )
    if row.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Response cannot be sent from status '{row.status}'",
        )
    if row.platform.name not in {"facebook", "instagram"}:
        raise HTTPException(
            status_code=422,
            detail="Publishing is only implemented for Facebook and Instagram",
        )
    if (
        row.platform.max_message_length
        and len(row.content) > row.platform.max_message_length
    ):
        raise HTTPException(
            status_code=422, detail="Response exceeds the platform character limit"
        )

    interaction = db.get(Interaction, row.responding_to_interaction_id)
    if interaction is None:
        raise HTTPException(
            status_code=409, detail="Response target interaction no longer exists"
        )
    account_id = (interaction.platform_metadata or {}).get("business_account_id")
    credentials = db.query(PlatformCredential).filter_by(
        platform_id=row.platform_id, is_active=True
    )
    if account_id:
        credential = credentials.filter_by(business_account_id=account_id).one_or_none()
        if credential is None:
            raise HTTPException(
                status_code=503, detail="The interaction's platform account is disconnected or paused"
            )
    else:
        candidates = credentials.all()
        if len(candidates) != 1:
            raise HTTPException(
                status_code=409,
                detail="Interaction account is unknown; exactly one active platform account is required",
            )
        credential = candidates[0]
    if not credential.access_token:
        raise HTTPException(status_code=503, detail="Platform account has no access token")
    try:
        access_token = decrypt_secret(credential.access_token)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if interaction.interaction_type == "message" and not row.is_private_message:
        raise HTTPException(status_code=422, detail="Messages require a private response")
    if row.is_private_message and interaction.interaction_type != "message":
        raise HTTPException(status_code=422, detail="Private replies to public interactions are not implemented")
    if not row.is_private_message and interaction.interaction_type != "comment":
        raise HTTPException(status_code=422, detail="Public publishing is only implemented for comments")
    if row.is_private_message:
        if row.platform.name == "instagram" and len(row.content.encode("utf-8")) > 1000:
            raise HTTPException(status_code=422, detail="Instagram messages must not exceed 1000 UTF-8 bytes")
        path = f"{credential.business_account_id}/messages" if row.platform.name == "facebook" else "me/messages"
        body = {
            "recipient": {"id": interaction.customer.platform_user_id},
            "message": {"text": row.content},
        }
        if row.platform.name == "facebook":
            body["messaging_type"] = "RESPONSE"
    else:
        if row.platform.name == "instagram":
            path = f"{interaction.platform_interaction_id}/replies"
        else:
            path = f"{interaction.platform_interaction_id}/comments"
        body = {"message": row.content}

    claimed = db.query(Response).filter(
        Response.id == row.id, Response.status == "draft"
    ).update({"status": "sending"}, synchronize_session="fetch")
    if not claimed:
        db.rollback()
        raise HTTPException(status_code=409, detail="Response is already being sent")
    db.commit()
    url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{path}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if row.is_private_message:
                platform_result = await client.post(
                    url, json=body, headers={"Authorization": f"Bearer {access_token}"}
                )
            else:
                platform_result = await client.post(
                    url, data=body, headers={"Authorization": f"Bearer {access_token}"}
                )
    except httpx.RequestError as exc:
        row.status = "failed" if isinstance(exc, httpx.ConnectError) else "unknown"
        row.error_message = (
            "Could not connect to the social platform"
            if row.status == "failed"
            else "Delivery status is unknown; check the social platform before sending again"
        )
        credential.sync_status = "error"
        credential.error_message = row.error_message
        create_audit(db, request, user, "response.publish_failed", "response", row.id)
        db.commit()
        raise HTTPException(status_code=502, detail=row.error_message) from exc
    if platform_result.is_error:
        row.status = "unknown" if platform_result.status_code >= 500 else "failed"
        row.error_message = (
            f"Platform returned HTTP {platform_result.status_code}; check delivery before sending again"
            if row.status == "unknown"
            else f"Platform returned HTTP {platform_result.status_code}"
        )
        row.platform_response = {"status_code": platform_result.status_code}
        credential.sync_status = "error"
        credential.error_message = row.error_message
        create_audit(db, request, user, "response.publish_failed", "response", row.id)
        db.commit()
        raise HTTPException(status_code=502, detail=row.error_message)
    try:
        result = platform_result.json()
    except ValueError as exc:
        row.status = "unknown"
        row.error_message = "Platform returned an unreadable success response; check delivery before sending again"
        create_audit(db, request, user, "response.publish_failed", "response", row.id)
        db.commit()
        raise HTTPException(status_code=502, detail=row.error_message) from exc
    if not isinstance(result, dict) or not (result.get("id") or result.get("message_id")):
        row.status = "unknown"
        row.error_message = "Platform returned no message ID; check delivery before sending again"
        create_audit(db, request, user, "response.publish_failed", "response", row.id)
        db.commit()
        raise HTTPException(status_code=502, detail=row.error_message)
    sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.status = "published"
    row.sent_at = sent_at
    row.platform_response = result
    row.platform_post_id = result.get("id") or result.get("message_id")
    row.error_message = None
    ticket.first_response_at = ticket.first_response_at or sent_at
    credential.last_sync_at = sent_at
    credential.sync_status = "active"
    credential.error_message = None
    create_audit(
        db,
        request,
        user,
        "response.published",
        "response",
        row.id,
        new_values={"platform_post_id": row.platform_post_id},
    )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "status": row.status,
        "platform_post_id": row.platform_post_id,
        "sent_at": row.sent_at,
    }
