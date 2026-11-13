from pydantic import BaseModel
from typing import Literal


class IntegrationStatus(BaseModel):
    status: Literal["connected", "configured", "not_configured", "error"]
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    dependencies: dict[str, IntegrationStatus]
