from fastapi import APIRouter

from src.core.config import settings
from src.integrations.foundry import foundry_configuration_status
from src.integrations.supabase import check_supabase_connection
from src.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def get_health() -> HealthResponse:
    dependencies = {
        "supabase": check_supabase_connection(),
        "foundry": foundry_configuration_status(),
    }
    status = "ok" if dependencies["supabase"].status == "connected" else "degraded"
    return HealthResponse(
        status=status,
        service=settings.app_name,
        environment=settings.environment,
        dependencies=dependencies,
    )
