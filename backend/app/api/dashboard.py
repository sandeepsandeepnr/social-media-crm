from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Interaction, Platform, Response, Ticket, User
from app.security import get_current_user

router = APIRouter()


def first_response_average(
    db: Session, since: datetime | None = None, until: datetime | None = None
):
    query = db.query(Ticket.opened_at, Ticket.first_response_at).filter(
        Ticket.first_response_at.is_not(None)
    )
    if since:
        query = query.filter(Ticket.opened_at >= since)
    if until:
        query = query.filter(Ticket.opened_at < until)
    values = [
        (responded - opened).total_seconds() / 60
        for opened, responded in query.all()
        if opened is not None and responded is not None
    ]
    return round(sum(values) / len(values), 2) if values else None


@router.get("/dashboard/metrics")
def dashboard_metrics(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_start = datetime.combine(now.date(), time.min)
    tickets_query = db.query(Ticket)
    interactions_query = db.query(Interaction)
    if user.role == "agent":
        tickets_query = tickets_query.filter(
            (Ticket.assigned_to_agent_id == user.id)
            | (Ticket.assigned_to_agent_id.is_(None))
        )
        interactions_query = interactions_query.join(
            Ticket, Ticket.primary_interaction_id == Interaction.id, isouter=True
        ).filter((Ticket.assigned_to_agent_id == user.id) | Ticket.id.is_(None))
    today_count = interactions_query.filter(
        Interaction.captured_at >= day_start
    ).count()
    unprocessed = interactions_query.filter(Interaction.is_processed.is_(False)).count()
    ticket_base = tickets_query
    open_count = ticket_base.filter(
        Ticket.status.in_(["open", "in_progress", "pending"])
    ).count()
    status_query = db.query(Ticket.status, func.count(Ticket.id))
    platform_ticket_query = db.query(Platform.name, func.count(Ticket.id)).join(
        Ticket, Ticket.platform_id == Platform.id
    )
    if user.role == "agent":
        status_query = status_query.filter(
            (Ticket.assigned_to_agent_id == user.id)
            | (Ticket.assigned_to_agent_id.is_(None))
        )
        platform_ticket_query = platform_ticket_query.filter(
            (Ticket.assigned_to_agent_id == user.id)
            | (Ticket.assigned_to_agent_id.is_(None))
        )
    by_status = {
        key: count for key, count in status_query.group_by(Ticket.status).all()
    }
    by_platform = {
        key: count for key, count in platform_ticket_query.group_by(Platform.name).all()
    }
    workload_query = (
        db.query(User, func.count(Ticket.id))
        .outerjoin(
            Ticket,
            (Ticket.assigned_to_agent_id == User.id)
            & Ticket.status.in_(["open", "in_progress", "pending"]),
        )
        .filter(User.role == "agent", User.is_active.is_(True))
    )
    if user.role == "agent":
        workload_query = workload_query.filter(User.id == user.id)
    workload = []
    for agent, count in workload_query.group_by(User.id).all():
        waiting = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.assigned_to_agent_id == agent.id,
                Ticket.status.in_(["open", "in_progress", "pending"]),
                Ticket.first_response_at.is_(None),
            )
            .scalar()
            or 0
        )
        workload.append(
            {"agent": agent.username, "open_tickets": count, "unresponded": waiting}
        )
    return {
        "total_interactions_today": today_count,
        "unprocessed_interactions": unprocessed,
        "open_tickets": open_count,
        "avg_first_response_time_minutes": first_response_average(db),
        "tickets_by_status": by_status,
        "tickets_by_platform": by_platform,
        "agent_workload": workload,
    }


@router.get("/analytics/platforms")
def platform_analytics(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400, detail="date_from must be on or before date_to"
        )
    start = datetime.combine(date_from, time.min) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None
    result = []
    platforms = db.query(Platform).order_by(Platform.name).all()
    for platform in platforms:
        interactions_query = db.query(func.count(Interaction.id)).filter(
            Interaction.platform_id == platform.id
        )
        tickets_query = db.query(Ticket).filter(Ticket.platform_id == platform.id)
        responses_query = db.query(Response).filter(
            Response.platform_id == platform.id, Response.status == "published"
        )
        if start:
            interactions_query = interactions_query.filter(
                Interaction.captured_at >= start
            )
            tickets_query = tickets_query.filter(Ticket.opened_at >= start)
            responses_query = responses_query.filter(Response.sent_at >= start)
        if end:
            interactions_query = interactions_query.filter(
                Interaction.captured_at < end
            )
            tickets_query = tickets_query.filter(Ticket.opened_at < end)
            responses_query = responses_query.filter(Response.sent_at < end)
        total_interactions = interactions_query.scalar() or 0
        total_tickets = tickets_query.count()
        response_times = db.query(Ticket.opened_at, Ticket.first_response_at).filter(
            Ticket.platform_id == platform.id, Ticket.first_response_at.is_not(None)
        )
        resolution_times = db.query(Ticket.opened_at, Ticket.resolved_at).filter(
            Ticket.platform_id == platform.id, Ticket.resolved_at.is_not(None)
        )
        if start:
            response_times = response_times.filter(Ticket.opened_at >= start)
            resolution_times = resolution_times.filter(Ticket.opened_at >= start)
        if end:
            response_times = response_times.filter(Ticket.opened_at < end)
            resolution_times = resolution_times.filter(Ticket.opened_at < end)
        response_durations = [
            (responded - opened).total_seconds() / 60
            for opened, responded in response_times.all()
            if opened is not None and responded is not None
        ]
        resolution_durations = [
            (resolved - opened).total_seconds() / 60
            for opened, resolved in resolution_times.all()
            if opened is not None and resolved is not None
        ]
        result.append(
            {
                "platform": platform.name,
                "total_interactions": total_interactions,
                "total_tickets": total_tickets,
                "avg_response_time_minutes": (
                    round(sum(response_durations) / len(response_durations), 2)
                    if response_durations
                    else None
                ),
                "avg_resolution_time_minutes": (
                    round(sum(resolution_durations) / len(resolution_durations), 2)
                    if resolution_durations
                    else None
                ),
            }
        )
    return {"data": result}
