from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Customer,
    Interaction,
    Platform,
    PlatformCredential,
    Response,
    Ticket,
    TicketInteraction,
    User,
)
from app.schemas import InteractionCreate, InteractionPatch
from app.security import get_current_user
from app.utils import create_audit, interaction_data

router = APIRouter()


def save_interaction(db: Session, data: dict) -> Interaction:
    platform = (
        db.query(Platform)
        .filter(Platform.name == data["platform"].lower())
        .one_or_none()
    )
    if platform is None:
        raise HTTPException(status_code=404, detail="Platform not found")
    account_id = data.get("business_account_id")
    if account_id:
        credential = (
            db.query(PlatformCredential)
            .filter_by(
                platform_id=platform.id,
                business_account_id=account_id,
                is_active=True,
            )
            .one_or_none()
        )
        if credential is None:
            raise HTTPException(status_code=400, detail="Active platform account not found")
    existing = (
        db.query(Interaction)
        .filter_by(
            platform_id=platform.id,
            platform_interaction_id=data["platform_interaction_id"],
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.customer.platform_user_id != data["platform_user_id"]:
            raise HTTPException(
                status_code=409, detail="Interaction already belongs to another customer"
            )
        existing_account = (existing.platform_metadata or {}).get("business_account_id")
        if account_id and existing_account and existing_account != account_id:
            raise HTTPException(
                status_code=409, detail="Interaction already belongs to another account"
            )
        if account_id and not existing_account:
            if not data.get("webhook_verified"):
                raise HTTPException(
                    status_code=409,
                    detail="Existing interaction has no verified account; manual capture cannot assign one",
                )
            existing.platform_metadata = {
                **(existing.platform_metadata or {}),
                "business_account_id": account_id,
            }
        return existing
    customer = (
        db.query(Customer)
        .filter_by(
            platform_id=platform.id,
            platform_user_id=data["platform_user_id"],
        )
        .one_or_none()
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if customer is None:
        customer = Customer(
            platform_id=platform.id,
            platform_user_id=data["platform_user_id"],
            display_name=data.get("customer_name"),
            avatar_url=data.get("avatar_url"),
            first_interaction_at=data.get("captured_at") or now,
            last_interaction_at=data.get("captured_at") or now,
        )
        db.add(customer)
        db.flush()
    else:
        if data.get("customer_name"):
            customer.display_name = data["customer_name"]
        if data.get("avatar_url"):
            customer.avatar_url = data["avatar_url"]
        customer.last_interaction_at = data.get("captured_at") or now
    metadata = dict(data.get("platform_metadata") or {})
    if account_id:
        metadata["business_account_id"] = account_id
    interaction = Interaction(
        platform_id=platform.id,
        platform_interaction_id=data["platform_interaction_id"],
        customer_id=customer.id,
        interaction_type=data["interaction_type"],
        content=data.get("content"),
        media_urls=data.get("media_urls") or [],
        post_url=data.get("post_url"),
        is_public=data.get("is_public", True),
        platform_metadata=metadata or None,
        captured_at=data.get("captured_at") or now,
    )
    db.add(interaction)
    db.flush()
    return interaction


@router.get("")
def list_interactions(
    status: str | None = None,
    platform: str | None = None,
    search: str | None = None,
    content_search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = "captured_at",
    order: str = "desc",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = (
        db.query(Interaction)
        .options(joinedload(Interaction.platform), joinedload(Interaction.customer))
        .join(Platform)
        .join(Customer)
    )
    if platform:
        query = query.filter(Platform.name == platform.lower())
    if status == "unprocessed":
        query = query.filter(Interaction.is_processed.is_(False))
    elif status == "processed":
        query = query.filter(Interaction.is_processed.is_(True))
    elif status:
        query = (
            query.join(
                TicketInteraction, TicketInteraction.interaction_id == Interaction.id
            )
            .join(Ticket, Ticket.id == TicketInteraction.ticket_id)
            .filter(Ticket.status == status)
        )
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(Interaction.content.ilike(term), Customer.display_name.ilike(term))
        )
    if content_search:
        if not content_search.strip():
            raise HTTPException(status_code=422, detail="Content search must not be blank")
        query = query.filter(Interaction.content.icontains(content_search.strip(), autoescape=True))
    sort_columns = {
        "created_at": Interaction.created_at,
        "captured_at": Interaction.captured_at,
    }
    if sort not in sort_columns or order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Unsupported sort field or order")
    total = query.with_entities(func.count(func.distinct(Interaction.id))).scalar() or 0
    sort_column = sort_columns[sort]
    query = query.order_by(
        sort_column.asc() if order == "asc" else sort_column.desc(),
        Interaction.id.asc() if order == "asc" else Interaction.id.desc(),
    )
    rows = query.offset(offset).limit(limit).all()
    unprocessed = (
        db.query(Interaction).filter(Interaction.is_processed.is_(False)).count()
    )
    return {
        "data": [interaction_data(db, row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "unprocessed_count": unprocessed,
    }


@router.post("", status_code=201)
def create_interaction(
    payload: InteractionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    interaction = save_interaction(db, payload.model_dump())
    if payload.business_account_id:
        from app.api.tickets import route_ticket

        credential = db.query(PlatformCredential).filter_by(
            platform_id=interaction.platform_id,
            business_account_id=payload.business_account_id,
            is_active=True,
        ).one()
        route_ticket(db, interaction, credential)
    create_audit(
        db, request, user, "interaction.captured", "interaction", interaction.id
    )
    db.commit()
    db.refresh(interaction)
    return interaction_data(db, interaction)


@router.get("/{interaction_id}")
def get_interaction(
    interaction_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    interaction = (
        db.query(Interaction)
        .options(joinedload(Interaction.platform), joinedload(Interaction.customer))
        .filter(Interaction.id == interaction_id)
        .one_or_none()
    )
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    links = (
        db.query(Ticket)
        .join(TicketInteraction, TicketInteraction.ticket_id == Ticket.id)
        .filter(TicketInteraction.interaction_id == interaction.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )
    ticket = links[0] if links else None
    thread = [
        {
            "id": str(interaction.id),
            "type": "customer",
            "content": interaction.content or "",
            "timestamp": interaction.captured_at,
        }
    ]
    if ticket:
        links = (
            db.query(TicketInteraction)
            .filter(TicketInteraction.ticket_id == ticket.id)
            .order_by(TicketInteraction.sequence_number)
            .all()
        )
        thread = [
            {
                "id": str(link.interaction.id),
                "type": "customer",
                "content": link.interaction.content or "",
                "timestamp": link.interaction.captured_at,
            }
            for link in links
        ]
        published = (
            db.query(Response)
            .filter(
                Response.ticket_id == ticket.id,
                Response.status == "published",
            )
            .all()
        )
        thread.extend(
            {
                "id": str(row.id),
                "type": "agent",
                "content": row.content,
                "timestamp": row.sent_at,
            }
            for row in published
        )
        thread.sort(key=lambda message: message["timestamp"] or datetime.min)
    response = {
        **interaction_data(db, interaction),
        "customer": {
            "id": str(interaction.customer.id),
            "name": interaction.customer.display_name or "Unknown",
            "avatar": interaction.customer.avatar_url,
            "follower_count": interaction.customer.follower_count,
            "platform_user_id": interaction.customer.platform_user_id,
        },
        "conversation_thread": thread,
        "ticket": (
            {
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "status": ticket.status,
            }
            if ticket
            else None
        ),
    }
    return response


@router.patch("/{interaction_id}")
def update_interaction(
    interaction_id: UUID,
    payload: InteractionPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    interaction = db.get(Interaction, interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    old_value = interaction.is_processed
    interaction.is_processed = payload.is_processed
    create_audit(
        db,
        request,
        user,
        "interaction.processed",
        "interaction",
        interaction.id,
        old_values={"is_processed": old_value},
        new_values={"is_processed": payload.is_processed},
    )
    db.commit()
    db.refresh(interaction)
    return interaction_data(db, interaction)
