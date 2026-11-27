import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: Literal["agent", "team_leader", "admin"] = "agent"

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("A valid email address is required")
        return normalized

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        if not any(char.islower() for char in value) or not any(
            char.isupper() for char in value
        ):
            raise ValueError("Password must contain uppercase and lowercase letters")
        if not any(char.isdigit() for char in value) or not any(
            not char.isalnum() for char in value
        ):
            raise ValueError("Password must contain a number and a special character")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshRequest(BaseModel):
    refresh_token: str


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)
    language_preference: str | None = Field(default=None, max_length=20)
    role: Literal["admin", "team_leader", "agent"] | None = None
    is_active: bool | None = None


class PlatformCredentialCreate(BaseModel):
    platform_id: UUID
    business_account_id: str = Field(min_length=1, max_length=255)
    business_account_name: str | None = Field(default=None, max_length=255)
    access_token: str = Field(min_length=1, max_length=2000)
    refresh_token: str | None = Field(default=None, max_length=2000)
    scope: str | None = Field(default=None, max_length=1000)
    token_expires_at: datetime | None = None


class PlatformCredentialUpdate(BaseModel):
    access_token: str | None = Field(default=None, min_length=1, max_length=2000)
    refresh_token: str | None = Field(default=None, max_length=2000)
    business_account_name: str | None = Field(default=None, max_length=255)
    scope: str | None = Field(default=None, max_length=1000)
    token_expires_at: datetime | None = None
    is_active: bool | None = None


class InteractionCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=50)
    business_account_id: str | None = Field(default=None, min_length=1, max_length=255)
    platform_interaction_id: str = Field(min_length=1, max_length=500)
    platform_user_id: str = Field(min_length=1, max_length=500)
    customer_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)
    interaction_type: Literal["comment", "message", "mention", "review", "post"]
    content: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    post_url: str | None = Field(default=None, max_length=500)
    is_public: bool = True
    captured_at: datetime | None = None


class InteractionPatch(BaseModel):
    is_processed: bool


class TicketCreate(BaseModel):
    primary_interaction_id: UUID
    subject: str | None = Field(default=None, max_length=500)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    assigned_to_agent_id: UUID | None = None


class TicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "pending", "resolved", "closed"] | None = (
        None
    )
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    assigned_to_agent_id: UUID | None = None
    internal_notes: str | None = None
    tags: list[str] | None = None
    subject: str | None = Field(default=None, max_length=500)


class TicketResolve(BaseModel):
    resolution_summary: str = Field(min_length=1, max_length=10000)


class TicketInteractionLink(BaseModel):
    interaction_id: UUID


class ResponseCreate(BaseModel):
    ticket_id: UUID
    responding_to_interaction_id: UUID | None = None
    content: str = Field(min_length=1, max_length=63206)
    is_private_message: bool = False


class ResponseUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=63206)


class SettingUpdate(BaseModel):
    values: dict[str, Any]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    data: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class Timestamped(BaseModel):
    created_at: datetime
