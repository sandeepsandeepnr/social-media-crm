from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Response, User
from app.schemas import UserUpdate
from app.security import get_current_user, require_roles
from app.utils import create_audit, user_data

router = APIRouter()


@router.get("")
def list_users(
    role: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    query = db.query(User)
    if role:
        if role not in {"admin", "team_leader", "agent"}:
            raise HTTPException(status_code=400, detail="Invalid role filter")
        query = query.filter(User.role == role)
    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "data": [user_data(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return user_data(current_user, include_profile=True)


@router.get("/{user_id}")
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user_data(user, include_profile=True)


@router.put("/{user_id}")
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and changes.get("is_active") is False:
        raise HTTPException(
            status_code=400, detail="You cannot deactivate your own account"
        )
    if user.id == admin.id and changes.get("role") not in {None, "admin"}:
        raise HTTPException(
            status_code=400, detail="You cannot remove your own administrator role"
        )
    old_values = {key: getattr(user, key) for key in changes}
    for key, value in changes.items():
        if value is not None or key == "is_active":
            setattr(user, key, value)
    create_audit(
        db,
        request,
        admin,
        "user.updated",
        "user",
        user.id,
        old_values=old_values,
        new_values=changes,
    )
    db.commit()
    db.refresh(user)
    return user_data(user, include_profile=True)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=400, detail="You cannot delete your own account"
        )
    if db.query(Response.id).filter(Response.agent_id == user.id).first():
        raise HTTPException(
            status_code=409,
            detail="This user has response history and cannot be deleted; deactivate the account instead",
        )
    create_audit(
        db,
        request,
        admin,
        "user.deleted",
        "user",
        user.id,
        old_values={"username": user.username},
    )
    db.delete(user)
    db.commit()
    return None
