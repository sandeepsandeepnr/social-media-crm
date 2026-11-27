from datetime import datetime, timedelta, timezone
import uuid

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RevokedToken, User
from app.schemas import LoginRequest, RefreshRequest, RegisterRequest
from app.security import (
    create_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.utils import create_audit, user_data
from config import settings

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter((User.email == payload.email) | (User.username == payload.username))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Username or email is already registered"
        )

    user_count = db.query(func.count(User.id)).scalar() or 0
    # Bootstrap the first account as the administrator; public registration cannot grant roles.
    role = "admin" if user_count == 0 else "agent"
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=role,
    )
    db.add(user)
    try:
        db.flush()
        create_audit(
            db,
            request,
            user,
            "user.registered",
            "user",
            user.id,
            new_values={"role": role},
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Username or email is already registered"
        ) from exc
    token = create_token(
        user, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh = create_token(
        user, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return {
        **user_data(user, include_profile=True),
        "token": token,
        "access_token": token,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if (
        user is None
        or not verify_password(payload.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    create_audit(db, request, user, "user.logged_in", "user", user.id)
    db.commit()
    token = create_token(
        user, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh = create_token(
        user, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return {
        "token": token,
        "access_token": token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user_data(user, include_profile=True),
    }


@router.post("/refresh")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        token_id = claims.get("jti")
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired refresh token"
        ) from exc
    if not token_id or db.get(RevokedToken, token_id) is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="User is inactive or no longer exists"
        )
    expires = claims.get("exp")
    db.add(
        RevokedToken(
            jti=token_id,
            expires_at=datetime.fromtimestamp(expires, timezone.utc).replace(
                tzinfo=None
            ),
        )
    )
    access = create_token(
        user, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh = create_token(
        user, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.commit()
    return {
        "token": access,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    request: Request,
    payload: RefreshRequest | None = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    claims = decode_token(token)
    expires = claims.get("exp")
    db.add(
        RevokedToken(
            jti=claims["jti"],
            expires_at=datetime.fromtimestamp(expires, timezone.utc).replace(
                tzinfo=None
            ),
        )
    )
    if payload and payload.refresh_token:
        try:
            refresh_claims = decode_token(payload.refresh_token)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=401, detail="Invalid refresh token"
            ) from exc
        if (
            refresh_claims.get("sub") != str(current_user.id)
            or refresh_claims.get("type") != "refresh"
        ):
            raise HTTPException(
                status_code=401, detail="Refresh token does not belong to this user"
            )
        db.add(
            RevokedToken(
                jti=refresh_claims["jti"],
                expires_at=datetime.fromtimestamp(
                    refresh_claims["exp"], timezone.utc
                ).replace(tzinfo=None),
            )
        )
    create_audit(db, request, current_user, "user.logged_out", "user", current_user.id)
    db.commit()
    return {"message": "Logged out successfully"}
