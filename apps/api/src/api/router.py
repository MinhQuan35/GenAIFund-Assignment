from fastapi import APIRouter

from src.api.routes import campaigns, health, integrations, messages

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(messages.router, tags=["messages"])
