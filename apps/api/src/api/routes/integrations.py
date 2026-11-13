from fastapi import APIRouter

from src.integrations.foundry import check_foundry_connection
from src.schemas.health import IntegrationStatus

router = APIRouter()


@router.post("/foundry/check", response_model=IntegrationStatus)
def check_foundry() -> IntegrationStatus:
    return check_foundry_connection()
