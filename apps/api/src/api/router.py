from fastapi import APIRouter

from src.api.routes import health, integrations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
