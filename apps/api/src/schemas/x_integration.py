from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=400)
    max_results: int = Field(default=25, ge=10, le=100)


class DiscoveryResponse(BaseModel):
    candidates_found: int
    saved: int
    query: str
    message: str


class SendMessageRequest(BaseModel):
    recipient_confirmed: bool


class XConnectionStatus(BaseModel):
    status: str
    username: str | None = None
    message: str
