import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RevokedToken, User
from config import settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_token(user: User, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "role": user.role,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise unauthorized
        token_id = payload.get("jti")
        subject = payload.get("sub")
        if not token_id or not subject:
            raise unauthorized
        if db.get(RevokedToken, token_id) is not None:
            raise unauthorized
        user = db.get(User, uuid.UUID(subject))
        if user is None or not user.is_active:
            raise unauthorized
        return user
    except (jwt.PyJWTError, ValueError):
        raise unauthorized


def require_roles(*roles: str):
    def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_dependency


def encrypt_secret(value: str) -> str:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key).encrypt(value.encode()).decode()


def require_credential_key() -> None:
    if settings.SECRET_KEY in {
        "your-secret-key-change-in-production",
        "your-super-secret-key-change-in-production-minimum-32-chars",
    } or len(settings.SECRET_KEY) < 32:
        raise HTTPException(
            status_code=503,
            detail="Configure a private SECRET_KEY of at least 32 characters before storing credentials",
        )


def decrypt_secret(value: str) -> str:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    try:
        return Fernet(key).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Stored platform credential cannot be decrypted; reconnect the account"
        ) from exc


def verify_webhook_signature(
    body: bytes, signature: str | None, app_secret: str | None
) -> bool:
    if not app_secret:
        return settings.DEBUG
    if not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), digest)
