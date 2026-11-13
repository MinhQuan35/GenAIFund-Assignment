import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    segment: str = Field(min_length=1, max_length=500)
    seed_accounts: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("seed_accounts")
    @classmethod
    def normalize_seed_accounts(cls, accounts: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for account in accounts:
            username = account.strip().lstrip("@").lower()
            if not re.fullmatch(r"[a-z0-9_]{1,15}", username):
                raise ValueError("Seed accounts must be X usernames, without URLs.")
            if username not in seen:
                seen.add(username)
                normalized.append(username)
        return normalized


class SeedAccount(BaseModel):
    username: str


class CampaignSummary(BaseModel):
    id: UUID
    name: str
    segment: str
    status: Literal["draft", "active", "paused", "archived"]
    seed_accounts: list[str]
    created_at: datetime
