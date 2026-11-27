from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Interaction,
    PlatformCredential,
    Response,
    SystemSetting,
    Ticket,
    TicketInteraction,
    User,
)
from app.schemas import TicketCreate, TicketInteractionLink, TicketResolve, TicketUpdate
from app.api.system_settings import DEFAULT_SETTINGS
from app.security import get_current_user
from app.utils import create_audit, ticket_detail, ticket_number, ticket_summary

router = APIRouter()


def route_ticket(db: Session, interaction: Interaction, credential: PlatformCredential) -> None:
    if db.query(TicketInteraction).filter_by(interaction_id=interaction.id).first():
        return
    setting = db.query(SystemSetting).filter_by(
        admin_id=credential.admin_id, setting_key="auto_create_tickets"
    ).one_or_none()
    if setting:
        if setting.setting_type != "boolean" or setting.setting_value not in {"true", "false"}:
            raise HTTPException(status_code=500, detail="Invalid automatic ticket setting")
        enabled = setting.setting_value == "true"
    else:
        enabled = DEFAULT_SETTINGS["auto_create_tickets"][1]
    if not enabled:
        return
    parent_id = (interaction.platform_metadata or {}).get("parent_id")
    if parent_id:
        candidates: set[UUID] = set()
        parent = db.query(Interaction).filter_by(
            platform_id=interaction.platform_id, platform_interaction_id=parent_id
        ).one_or_none()
        if (
            parent is not None
            and parent.id != interaction.id
            and parent.customer_id == interaction.customer_id
            and (parent.platform_metadata or {}).get("business_account_id")
            == credential.business_account_id
        ):
            link = db.query(TicketInteraction).filter_by(interaction_id=parent.id).one_or_none()
            if link:
                candidates.add(link.ticket_id)
        responses = db.query(Response).filter_by(
            platform_id=interaction.platform_id, platform_post_id=parent_id, status="published"
        ).all()
        for response in responses:
            target = db.get(Interaction, response.responding_to_interaction_id)
            ticket = db.get(Ticket, response.ticket_id)
            if (
                target and ticket
                and ticket.customer_id == interaction.customer_id
                and (target.platform_metadata or {}).get("business_account_id")
                == credential.business_account_id
            ):
                candidates.add(ticket.id)
        if len(candidates) == 1:
            ticket = db.get(Ticket, next(iter(candidates)))
            if ticket and ticket.status in {"open", "in_progress", "pending"}:
                sequence = (
                    db.query(func.max(TicketInteraction.sequence_number))
                    .filter_by(ticket_id=ticket.id)
                    .scalar()
                    or 0
                ) + 1
                db.add(
                    TicketInteraction(
                        ticket_id=ticket.id,
                        interaction_id=interaction.id,
                        sequence_number=sequence,
                    )
                )
                interaction.is_processed = True
                db.flush()
                return
    create_ticket_for_interaction(db, interaction)
    db.flush()


def create_ticket_for_interaction(
    db: Session,
    interaction: Interaction,
    subject: str | None = None,
    priority: str = "medium",
    assigned_id: UUID | None = None,
) -> Ticket:
    number = ticket_number()
    for _ in range(5):
        if db.query(Ticket.id).filter(Ticket.ticket_number == number).first() is None:
            break
        number = ticket_number()
    else:
        raise HTTPException(
            status_code=503, detail="Unable to allocate a unique ticket number"
        )
    ticket = Ticket(
        ticket_number=number,
        customer_id=interaction.customer_id,
        primary_interaction_id=interaction.id,
        platform_id=interaction.platform_id,
        assigned_to_agent_id=assigned_id,
        status="open",
        priority=priority,
        subject=subject or (interaction.content or "Customer interaction")[:500],
        description=interaction.content,
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketInteraction(ticket_id=ticket.id, interaction_id=interaction.id, sequence_number=1)
    )
    interaction.is_processed = True
    return ticket


def accessible_ticket(db: Session, ticket_id: UUID, user: User) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.platform),
            joinedload(Ticket.assigned_agent),
        )
        .filter(Ticket.id == ticket_id)
        .one_or_none()
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if user.role == "agent" and ticket.assigned_to_agent_id not in {None, user.id}:
        raise HTTPException(
            status_code=403, detail="Ticket is assigned to another agent"
        )
    return ticket


@router.get("")
def list_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    platform: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = "opened_at",
    order: str = "desc",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Ticket).options(
        joinedload(Ticket.customer),
        joinedload(Ticket.platform),
        joinedload(Ticket.assigned_agent),
    )
    if user.role == "agent":
        query = query.filter(
            (Ticket.assigned_to_agent_id == user.id)
            | (Ticket.assigned_to_agent_id.is_(None))
        )
    if platform:
        query = query.join(Ticket.platform).filter_by(name=platform.lower())
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    sort_columns = {
        "opened_at": Ticket.opened_at,
        "created_at": Ticket.created_at,
        "updated_at": Ticket.updated_at,
    }
    if sort not in sort_columns or order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Unsupported sort field or order")
    total = query.count()
    col = sort_columns[sort]
    rows = (
        query.order_by(
            col.asc() if order == "asc" else col.desc(),
            Ticket.id.asc() if order == "asc" else Ticket.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    counts_query = db.query(Ticket.status, func.count(Ticket.id))
    if platform:
        from app.models import Platform

        counts_query = counts_query.join(Platform).filter(
            Platform.name == platform.lower()
        )
    if user.role == "agent":
        counts_query = counts_query.filter(
            (Ticket.assigned_to_agent_id == user.id)
            | (Ticket.assigned_to_agent_id.is_(None))
        )
    counts = {key: count for key, count in counts_query.group_by(Ticket.status).all()}
    return {
        "data": [ticket_summary(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "by_status": counts,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    interaction = (
        db.query(Interaction)
        .filter(Interaction.id == payload.primary_interaction_id)
        .one_or_none()
    )
    if interaction is None:
        raise HTTPException(status_code=404, detail="Primary interaction not found")
    linked = (
        db.query(TicketInteraction).filter_by(interaction_id=interaction.id).first()
    )
    if linked:
        raise HTTPException(
            status_code=409, detail="Interaction already belongs to a ticket"
        )
    assigned_id = payload.assigned_to_agent_id
    if assigned_id and user.role == "agent" and assigned_id != user.id:
        raise HTTPException(
            status_code=403, detail="Agents can only assign tickets to themselves"
        )
    if assigned_id:
        assignee = db.get(User, assigned_id)
        if assignee is None or assignee.role != "agent" or not assignee.is_active:
            raise HTTPException(
                status_code=400, detail="Assignee must be an active agent"
            )
    ticket = create_ticket_for_interaction(
        db, interaction, payload.subject, payload.priority, assigned_id
    )
    create_audit(
        db,
        request,
        user,
        "ticket.created",
        "ticket",
        ticket.id,
        new_values={"ticket_number": ticket.ticket_number},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if db.query(TicketInteraction).filter_by(interaction_id=interaction.id).first():
            raise HTTPException(status_code=409, detail="Interaction already belongs to a ticket") from exc
        raise
    db.refresh(ticket)
    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "status": ticket.status,
        "created_at": ticket.created_at,
    }


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = accessible_ticket(db, ticket_id, user)
    return ticket_detail(db, ticket)


@router.put("/{ticket_id}")
def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = accessible_ticket(db, ticket_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No ticket fields were supplied")
    assigned_id = changes.get("assigned_to_agent_id")
    if "assigned_to_agent_id" in changes:
        if user.role == "agent" and assigned_id not in {None, user.id}:
            raise HTTPException(
                status_code=403, detail="Agents cannot assign tickets to another user"
            )
        if assigned_id:
            assignee = db.get(User, assigned_id)
            if assignee is None or assignee.role != "agent" or not assignee.is_active:
                raise HTTPException(
                    status_code=400, detail="Assignee must be an active agent"
                )
    old_values = {key: getattr(ticket, key) for key in changes}
    for key, value in changes.items():
        setattr(ticket, key, value)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if changes.get("status") == "resolved":
        ticket.resolved_at = ticket.resolved_at or now
    if changes.get("status") == "closed":
        ticket.closed_at = ticket.closed_at or now
    create_audit(
        db,
        request,
        user,
        "ticket.updated",
        "ticket",
        ticket.id,
        old_values=old_values,
        new_values=changes,
    )
    db.commit()
    db.refresh(ticket)
    return ticket_detail(db, ticket)


@router.put("/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: UUID,
    payload: TicketResolve,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = accessible_ticket(db, ticket_id, user)
    ticket.status = "resolved"
    ticket.resolved_at = ticket.resolved_at or datetime.now(timezone.utc).replace(
        tzinfo=None
    )
    ticket.resolution_summary = payload.resolution_summary
    create_audit(
        db,
        request,
        user,
        "ticket.resolved",
        "ticket",
        ticket.id,
        new_values={"resolution_summary": payload.resolution_summary},
    )
    db.commit()
    db.refresh(ticket)
    return {
        "id": str(ticket.id),
        "status": ticket.status,
        "resolved_at": ticket.resolved_at,
        "resolution_summary": ticket.resolution_summary,
    }


@router.post("/{ticket_id}/interactions", status_code=status.HTTP_201_CREATED)
def link_interaction(
    ticket_id: UUID,
    payload: TicketInteractionLink,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = accessible_ticket(db, ticket_id, user)
    interaction = db.get(Interaction, payload.interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    if (
        interaction.customer_id != ticket.customer_id
        or interaction.platform_id != ticket.platform_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Interaction must belong to the same customer and platform",
        )
    primary = db.get(Interaction, ticket.primary_interaction_id)
    primary_account = (primary.platform_metadata or {}).get("business_account_id") if primary else None
    interaction_account = (interaction.platform_metadata or {}).get("business_account_id")
    if primary_account and interaction_account and primary_account != interaction_account:
        raise HTTPException(status_code=400, detail="Interactions belong to different platform accounts")
    if (
        db.query(TicketInteraction)
        .filter_by(interaction_id=interaction.id)
        .first()
    ):
        raise HTTPException(
            status_code=409, detail="Interaction already belongs to a ticket"
        )
    sequence = (
        db.query(func.max(TicketInteraction.sequence_number))
        .filter(TicketInteraction.ticket_id == ticket.id)
        .scalar()
        or 0
    ) + 1
    db.add(
        TicketInteraction(
            ticket_id=ticket.id, interaction_id=interaction.id, sequence_number=sequence
        )
    )
    interaction.is_processed = True
    create_audit(
        db,
        request,
        user,
        "ticket.interaction_linked",
        "ticket",
        ticket.id,
        new_values={"interaction_id": str(interaction.id)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if db.query(TicketInteraction).filter_by(interaction_id=interaction.id).first():
            raise HTTPException(status_code=409, detail="Interaction already belongs to a ticket") from exc
        raise
    return {
        "ticket_id": str(ticket.id),
        "interaction_id": str(interaction.id),
        "sequence_number": sequence,
    }


@router.get("/{ticket_id}/responses")
def ticket_responses(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = accessible_ticket(db, ticket_id, user)
    responses = (
        db.query(Response)
        .filter(Response.ticket_id == ticket.id)
        .order_by(Response.created_at)
        .all()
    )
    return {
        "data": [
            {
                "id": str(row.id),
                "content": row.content,
                "status": row.status,
                "agent": row.agent.username,
                "sent_at": row.sent_at,
                "created_at": row.created_at,
                "responding_to_interaction_id": str(row.responding_to_interaction_id),
                "is_private_message": row.is_private_message,
                "error_message": row.error_message,
            }
            for row in responses
        ]
    }
