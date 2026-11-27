import json
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Interaction,
    Platform,
    Response,
    Ticket,
    TicketInteraction,
    User,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ticket_number() -> str:
    return f"TKT-{secrets.randbelow(1_000_000):06d}"


def create_audit(
    db: Session,
    request: Request,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: UUID | str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            old_values=old_values,
            new_values=new_values,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )


def platform_data(platform: Platform) -> dict[str, Any]:
    return {
        "id": str(platform.id),
        "name": platform.name,
        "display_name": platform.display_name,
        "icon_url": platform.icon_url,
        "is_active": platform.is_active,
        "supports_media": platform.supports_media,
        "max_message_length": platform.max_message_length,
    }


def user_data(user: User, include_profile: bool = False) -> dict[str, Any]:
    result = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
    if include_profile:
        result.update(
            first_name=user.first_name,
            last_name=user.last_name,
            timezone=user.timezone,
            language_preference=user.language_preference,
            last_login=user.last_login,
            is_verified=user.is_verified,
        )
    return result


def customer_data(customer) -> dict[str, Any]:
    return {
        "id": str(customer.id),
        "name": customer.display_name or "Unknown",
        "platform_user_id": customer.platform_user_id,
        "avatar": customer.avatar_url,
        "profile_url": customer.profile_url,
        "follower_count": customer.follower_count,
        "is_verified": customer.is_verified_on_platform,
        "platform": customer.platform.name if customer.platform else None,
        "first_interaction_at": customer.first_interaction_at,
        "last_interaction_at": customer.last_interaction_at,
    }


def interaction_data(db: Session, interaction: Interaction) -> dict[str, Any]:
    links = (
        db.query(TicketInteraction, Ticket)
        .join(Ticket, Ticket.id == TicketInteraction.ticket_id)
        .filter(TicketInteraction.interaction_id == interaction.id)
        .order_by(TicketInteraction.sequence_number)
        .all()
    )
    ticket_link = links[0][1] if links else None
    return {
        "id": str(interaction.id),
        "platform": interaction.platform.name,
        "customer_name": interaction.customer.display_name or "Unknown",
        "customer_avatar": interaction.customer.avatar_url,
        "interaction_type": interaction.interaction_type,
        "content": interaction.content or "",
        "media_urls": interaction.media_urls or [],
        "post_url": interaction.post_url,
        "captured_at": interaction.captured_at,
        "ticket_id": str(ticket_link.id) if ticket_link else None,
        "status": (
            ticket_link.status
            if ticket_link
            else ("processed" if interaction.is_processed else "unprocessed")
        ),
        "is_public": interaction.is_public,
        "is_processed": interaction.is_processed,
    }


def ticket_summary(ticket: Ticket) -> dict[str, Any]:
    opened = ticket.opened_at
    response_minutes = None
    if opened and ticket.first_response_at:
        response_minutes = max(
            0, int((ticket.first_response_at - opened).total_seconds() // 60)
        )
    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "customer_name": ticket.customer.display_name or "Unknown",
        "platform": ticket.platform.name,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": (
            ticket.assigned_agent.username if ticket.assigned_agent else None
        ),
        "opened_at": opened,
        "first_response_at": ticket.first_response_at,
        "response_time_minutes": response_minutes,
    }


def ticket_detail(db: Session, ticket: Ticket) -> dict[str, Any]:
    links = (
        db.query(TicketInteraction)
        .filter(TicketInteraction.ticket_id == ticket.id)
        .order_by(TicketInteraction.sequence_number)
        .all()
    )
    interactions = []
    for link in links:
        item = link.interaction
        interactions.append(
            {
                "id": str(item.id),
                "type": item.interaction_type,
                "content": item.content or "",
                "timestamp": item.captured_at,
                "platform_url": item.post_url,
                "source": "customer",
            }
        )
    responses = (
        db.query(Response)
        .filter(Response.ticket_id == ticket.id, Response.status == "published")
        .order_by(Response.sent_at)
        .all()
    )
    for response in responses:
        interactions.append(
            {
                "id": str(response.id),
                "type": "agent",
                "content": response.content,
                "timestamp": response.sent_at,
                "sent_at": response.sent_at,
                "source": "agent",
            }
        )
    interactions.sort(key=lambda item: item["timestamp"] or datetime.min)
    assigned = None
    if ticket.assigned_agent:
        assigned = {
            "id": str(ticket.assigned_agent.id),
            "username": ticket.assigned_agent.username,
            "name": " ".join(
                filter(
                    None,
                    [ticket.assigned_agent.first_name, ticket.assigned_agent.last_name],
                )
            ),
        }
    return {
        **ticket_summary(ticket),
        "customer": customer_data(ticket.customer),
        "description": ticket.description,
        "assigned_to": assigned,
        "assigned_to_agent_id": (
            str(ticket.assigned_to_agent_id) if ticket.assigned_to_agent_id else None
        ),
        "tags": ticket.tags or [],
        "conversation": interactions,
        "opened_at": ticket.opened_at,
        "first_response_at": ticket.first_response_at,
        "resolved_at": ticket.resolved_at,
        "closed_at": ticket.closed_at,
        "internal_notes": ticket.internal_notes,
        "resolution_summary": ticket.resolution_summary,
        "created_at": ticket.created_at,
    }


def safe_setting_value(value: str | None, value_type: str | None) -> Any:
    if value_type == "boolean":
        return value == "true"
    if value_type == "integer":
        return int(value or 0)
    if value_type == "json":
        return json.loads(value or "null")
    return value
