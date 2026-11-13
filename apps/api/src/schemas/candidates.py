import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_url: HttpUrl
    source_type: Literal["profile", "post", "website", "other"]
    excerpt: str = Field(min_length=1, max_length=3000)


class CandidateCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=15)
    display_name: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=160)
    profile_url: HttpUrl | None = None
    fit_reason: str = Field(min_length=1, max_length=1000)
    fit_score: int | None = Field(default=None, ge=0, le=100)
    evidence: list[EvidenceCreate] = Field(min_length=1, max_length=20)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, username: str) -> str:
        normalized = username.strip().lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9_]{1,15}", normalized):
            raise ValueError("Enter an X username, not a URL.")
        return normalized


class EvidenceResponse(BaseModel):
    id: UUID
    source_url: str
    source_type: str
    excerpt: str
    captured_at: datetime


from src.schemas.messages import MessageDraftResponse


class CandidateWorkspaceItem(BaseModel):
    id: UUID
    username: str
    display_name: str | None
    bio: str | None
    location: str | None
    profile_url: str | None
    fit_reason: str
    fit_score: int | None
    status: str
    evidence: list[EvidenceResponse]
    message: MessageDraftResponse | None


class CampaignWorkspace(BaseModel):
    id: UUID
    name: str
    segment: str
    status: str
    seed_accounts: list[str]
    candidates: list[CandidateWorkspaceItem]


