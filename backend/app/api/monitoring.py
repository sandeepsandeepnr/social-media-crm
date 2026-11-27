from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    InstagramHashtagCredential,
    MonitoringTerm,
    PlatformCredential,
    User,
)
from app.security import (
    decrypt_secret,
    encrypt_secret,
    get_current_user,
    require_credential_key,
    require_roles,
)
from app.utils import create_audit
from config import settings

router = APIRouter()


class TermCreate(BaseModel):
    term: str = Field(min_length=1, max_length=100)

    @field_validator("term")
    @classmethod
    def clean_term(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Term must not be blank")
        return value


class HashtagTokenUpdate(BaseModel):
    access_token: str = Field(min_length=1, max_length=2000)

    @field_validator("access_token")
    @classmethod
    def clean_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Access token must not be blank")
        return value


class HashtagSearch(BaseModel):
    credential_id: UUID
    hashtag: str = Field(min_length=1, max_length=100)

    @field_validator("hashtag")
    @classmethod
    def clean_hashtag(cls, value: str) -> str:
        value = value.strip().removeprefix("#")
        if not value or any(not (char.isalnum() or char == "_") for char in value):
            raise ValueError(
                "Use a hashtag containing only letters, numbers, and underscores"
            )
        return value


def term_data(term: MonitoringTerm) -> dict:
    return {"id": str(term.id), "term": term.term, "created_at": term.created_at}


@router.get("/terms")
def list_terms(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(MonitoringTerm).order_by(MonitoringTerm.normalized_term).all()
    return {"data": [term_data(row) for row in rows]}


@router.post("/terms", status_code=201)
def create_term(
    payload: TermCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    normalized = payload.term.casefold()
    if db.query(MonitoringTerm).filter_by(normalized_term=normalized).first():
        raise HTTPException(
            status_code=409, detail="This monitoring term already exists"
        )
    row = MonitoringTerm(term=payload.term, normalized_term=normalized)
    db.add(row)
    try:
        db.flush()
        create_audit(
            db, request, admin, "monitoring.term_created", "monitoring_term", row.id
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if db.query(MonitoringTerm).filter_by(normalized_term=normalized).first():
            raise HTTPException(
                status_code=409, detail="This monitoring term already exists"
            ) from exc
        raise
    db.refresh(row)
    return term_data(row)


@router.delete("/terms/{term_id}", status_code=204)
def delete_term(
    term_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.get(MonitoringTerm, term_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Monitoring term not found")
    create_audit(
        db, request, admin, "monitoring.term_deleted", "monitoring_term", row.id
    )
    db.delete(row)
    db.commit()


@router.get("/instagram-accounts")
def instagram_accounts(
    db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))
):
    rows = (
        db.query(PlatformCredential)
        .filter(
            PlatformCredential.platform.has(name="instagram"),
            PlatformCredential.is_active.is_(True),
        )
        .order_by(PlatformCredential.business_account_name)
        .all()
    )
    return {
        "data": [
            {
                "id": str(row.id),
                "account_name": row.business_account_name,
                "account_id": row.business_account_id,
                "hashtag_token_configured": db.get(InstagramHashtagCredential, row.id)
                is not None,
            }
            for row in rows
        ]
    }


@router.put("/instagram-accounts/{credential_id}/hashtag-token")
def set_hashtag_token(
    credential_id: UUID,
    payload: HashtagTokenUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    require_credential_key()
    credential = db.get(PlatformCredential, credential_id)
    if credential is None or credential.platform.name != "instagram":
        raise HTTPException(status_code=404, detail="Instagram account not found")
    token = db.get(InstagramHashtagCredential, credential.id)
    if token is None:
        token = InstagramHashtagCredential(platform_credential_id=credential.id)
        db.add(token)
    token.access_token = encrypt_secret(payload.access_token)
    create_audit(
        db,
        request,
        admin,
        "monitoring.hashtag_token_updated",
        "platform_credential",
        credential.id,
    )
    db.commit()
    return {"configured": True}


@router.delete("/instagram-accounts/{credential_id}/hashtag-token", status_code=204)
def remove_hashtag_token(
    credential_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    token = db.get(InstagramHashtagCredential, credential_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Hashtag token not found")
    create_audit(
        db,
        request,
        admin,
        "monitoring.hashtag_token_deleted",
        "platform_credential",
        credential_id,
    )
    db.delete(token)
    db.commit()


async def graph_get(
    client: httpx.AsyncClient, path: str, params: dict[str, str], token: str
) -> dict:
    url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{path}"
    try:
        result = await client.get(
            url, params=params, headers={"Authorization": f"Bearer {token}"}
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach Meta; try again later"
        ) from exc
    if not 200 <= result.status_code < 300:
        raise HTTPException(
            status_code=502,
            detail=f"Meta rejected the request (HTTP {result.status_code}); check permissions and limits",
        )
    try:
        data = result.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="Meta returned an invalid response"
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Meta returned an invalid response")
    return data


@router.post("/accounts/{credential_id}/verify")
async def verify_account(
    credential_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    credential = db.get(PlatformCredential, credential_id)
    if (
        credential is None
        or credential.platform.name not in {"facebook", "instagram"}
        or not credential.is_active
    ):
        raise HTTPException(status_code=404, detail="Active Meta account not found")
    account_id = credential.business_account_id
    if not account_id.isascii() or not account_id.isdigit():
        raise HTTPException(status_code=422, detail="Meta account ID must be numeric")
    if not credential.access_token:
        raise HTTPException(
            status_code=503, detail="Platform account has no access token"
        )
    try:
        token = decrypt_secret(credential.access_token)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    async with httpx.AsyncClient(timeout=20.0) as client:
        result = await graph_get(client, account_id, {"fields": "id"}, token)
    if result.get("id") != account_id:
        raise HTTPException(
            status_code=502, detail="Meta returned an unexpected account ID"
        )
    return {
        "verified": True,
        "scope": "Account ID is readable; webhook, messaging and publishing permissions are not verified",
    }


@router.post("/instagram-hashtags/search")
async def search_instagram_hashtag(
    payload: HashtagSearch,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    credential = db.get(PlatformCredential, payload.credential_id)
    if (
        credential is None
        or credential.platform.name != "instagram"
        or not credential.is_active
    ):
        raise HTTPException(
            status_code=404, detail="Active Instagram account not found"
        )
    if (
        not credential.business_account_id.isascii()
        or not credential.business_account_id.isdigit()
    ):
        raise HTTPException(
            status_code=422, detail="Instagram account ID must be numeric"
        )
    stored = db.get(InstagramHashtagCredential, credential.id)
    if stored is None:
        raise HTTPException(
            status_code=400,
            detail="Configure a hashtag user access token for this account",
        )
    try:
        token = decrypt_secret(stored.access_token)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    async with httpx.AsyncClient(timeout=20.0) as client:
        found = await graph_get(
            client,
            "ig_hashtag_search",
            {
                "user_id": credential.business_account_id,
                "q": payload.hashtag,
            },
            token,
        )
        records = found.get("data")
        if (
            not isinstance(records, list)
            or len(records) != 1
            or not isinstance(records[0], dict)
        ):
            raise HTTPException(
                status_code=502, detail="Meta did not return a hashtag ID"
            )
        hashtag_id = records[0].get("id")
        if (
            not isinstance(hashtag_id, str)
            or not hashtag_id.isascii()
            or not hashtag_id.isdigit()
        ):
            raise HTTPException(
                status_code=502, detail="Meta returned an invalid hashtag ID"
            )
        result = await graph_get(
            client,
            f"{hashtag_id}/recent_media",
            {
                "user_id": credential.business_account_id,
                "fields": "id,caption,media_type,permalink,timestamp",
                "limit": "50",
            },
            token,
        )
    media = result.get("data")
    if not isinstance(media, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("id"), str)
        or any(
            item.get(key) is not None and not isinstance(item.get(key), str)
            for key in ("caption", "media_type", "permalink", "timestamp")
        )
        for item in media
    ):
        raise HTTPException(
            status_code=502, detail="Meta returned an invalid media list"
        )
    paging = result.get("paging")
    return {
        "hashtag": payload.hashtag,
        "data": [
            {
                key: item.get(key)
                for key in ("id", "caption", "media_type", "permalink", "timestamp")
            }
            for item in media
        ],
        "has_more": isinstance(paging, dict) and bool(paging.get("next")),
    }
