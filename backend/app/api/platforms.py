from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InstagramHashtagCredential, Platform, PlatformCredential, User
from app.schemas import PlatformCredentialCreate, PlatformCredentialUpdate
from app.security import encrypt_secret, require_credential_key, require_roles
from app.utils import create_audit, platform_data

router = APIRouter()


def credential_data(credential: PlatformCredential) -> dict:
    return {
        "id": str(credential.id),
        "platform_id": str(credential.platform_id),
        "platform": credential.platform.name,
        "business_account_id": credential.business_account_id,
        "business_account_name": credential.business_account_name,
        "is_active": credential.is_active,
        "sync_status": credential.sync_status,
        "last_sync_at": credential.last_sync_at,
        "token_expires_at": credential.token_expires_at,
        "scope": credential.scope,
        "created_at": credential.created_at,
    }


@router.get("/platforms")
def list_platforms(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "team_leader", "agent")),
):
    rows = db.query(Platform).order_by(Platform.display_name).all()
    return {"data": [platform_data(row) for row in rows]}


@router.post("/platform-credentials", status_code=status.HTTP_201_CREATED)
def connect_platform(
    payload: PlatformCredentialCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    require_credential_key()
    platform = db.get(Platform, payload.platform_id)
    if platform is None:
        raise HTTPException(status_code=404, detail="Platform not found")
    if not platform.is_active:
        raise HTTPException(
            status_code=400, detail="This platform is not enabled for integrations"
        )
    if (
        db.query(PlatformCredential)
        .filter_by(
            platform_id=platform.id, business_account_id=payload.business_account_id
        )
        .first()
    ):
        raise HTTPException(
            status_code=409, detail="This platform account is already connected"
        )
    credential = PlatformCredential(
        platform_id=platform.id,
        admin_id=admin.id,
        business_account_id=payload.business_account_id,
        business_account_name=payload.business_account_name,
        access_token=encrypt_secret(payload.access_token),
        refresh_token=(
            encrypt_secret(payload.refresh_token) if payload.refresh_token else None
        ),
        scope=payload.scope,
        token_expires_at=payload.token_expires_at,
        is_active=True,
        sync_status="active",
    )
    db.add(credential)
    create_audit(
        db,
        request,
        admin,
        "platform.connected",
        "platform_credential",
        credential.id,
        new_values={"platform": platform.name, "account": payload.business_account_id},
    )
    db.commit()
    db.refresh(credential)
    return credential_data(credential)


@router.get("/platform-credentials")
def list_credentials(
    platform: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "team_leader")),
):
    query = db.query(PlatformCredential).join(Platform)
    if platform:
        query = query.filter(Platform.name == platform.lower())
    return {
        "data": [credential_data(row) for row in query.order_by(Platform.name).all()]
    }


@router.put("/platform-credentials/{credential_id}")
def update_credential(
    credential_id: UUID,
    payload: PlatformCredentialUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    credential = db.get(PlatformCredential, credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Platform credential not found")
    changes = payload.model_dump(exclude_unset=True)
    if any(changes.get(key) for key in ("access_token", "refresh_token")):
        require_credential_key()
    old_values = {
        key: getattr(credential, key)
        for key in changes
        if key not in {"access_token", "refresh_token"}
    }
    for key, value in changes.items():
        if key in {"access_token", "refresh_token"} and value:
            setattr(credential, key, encrypt_secret(value))
        elif value is not None or key == "is_active":
            setattr(credential, key, value)
    if "is_active" in changes:
        credential.sync_status = "active" if credential.is_active else "paused"
    create_audit(
        db,
        request,
        admin,
        "platform.credentials_updated",
        "platform_credential",
        credential.id,
        old_values=old_values,
        new_values={
            key: ("[updated]" if key in {"access_token", "refresh_token"} else value)
            for key, value in changes.items()
        },
    )
    db.commit()
    db.refresh(credential)
    return credential_data(credential)


@router.delete(
    "/platform-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT
)
def disconnect_platform(
    credential_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    credential = db.get(PlatformCredential, credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Platform credential not found")
    create_audit(
        db,
        request,
        admin,
        "platform.disconnected",
        "platform_credential",
        credential.id,
    )
    hashtag_credential = db.get(InstagramHashtagCredential, credential.id)
    if hashtag_credential:
        db.delete(hashtag_credential)
    db.delete(credential)
    db.commit()
    return None
