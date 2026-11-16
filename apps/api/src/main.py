from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.router import api_router
from src.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend for the GenAI Fund outreach workspace.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.is_dir():
        application.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return application


app = create_app()
