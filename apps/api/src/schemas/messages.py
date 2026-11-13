from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MessageDraftResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    candidate_id: UUID
    content: str
    status: Literal["draft", "approved", "rejected", "send_pending", "sent", "replied", "failed"]
    created_at: datetime


class MessageEdit(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, content: str) -> str:
        return content.strip()


class MessageReview(BaseModel):
    action: Literal["approve", "reject"]
