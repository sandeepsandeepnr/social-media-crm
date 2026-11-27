from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Interaction, Ticket, User
from app.security import get_current_user
from app.utils import customer_data

router = APIRouter()


@router.get("")
def list_customers(
    search: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Customer)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.display_name.ilike(term), Customer.platform_user_id.ilike(term)
            )
        )
    total = query.count()
    rows = (
        query.order_by(Customer.last_interaction_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "data": [
            {
                **customer_data(row),
                "total_interactions": db.query(func.count(Interaction.id))
                .filter(Interaction.customer_id == row.id)
                .scalar()
                or 0,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{customer_id}")
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    interaction_count = (
        db.query(func.count(Interaction.id))
        .filter(Interaction.customer_id == customer.id)
        .scalar()
        or 0
    )
    open_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.customer_id == customer.id,
            Ticket.status.in_(["open", "in_progress", "pending"]),
        )
        .scalar()
        or 0
    )
    interactions = (
        db.query(Interaction)
        .filter(Interaction.customer_id == customer.id)
        .order_by(Interaction.captured_at.desc())
        .limit(50)
        .all()
    )
    sentiment = customer.sentiment_history or {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
    }
    return {
        **customer_data(customer),
        "total_interactions": interaction_count,
        "open_tickets": open_tickets,
        "sentiment_summary": sentiment,
        "interaction_history": [
            {
                "id": str(row.id),
                "type": row.interaction_type,
                "content": row.content or "",
                "timestamp": row.captured_at,
            }
            for row in interactions
        ],
    }
