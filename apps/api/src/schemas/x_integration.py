from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=400)
    target_users: int = Field(default=20, ge=1, le=100)


class DiscoveryResponse(BaseModel):
    requested: int
    candidates_found: int
    saved: int
    excluded: int
    pages_read: int
    query: str
    message: str


class SendMessageRequest(BaseModel):
    recipient_confirmed: bool


class XConnectionStatus(BaseModel):
    status: str
    username: str | None = None
    message: str
