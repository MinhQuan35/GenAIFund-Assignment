from fastapi import APIRouter

from src.core.config import settings
from src.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, environment=settings.environment)
