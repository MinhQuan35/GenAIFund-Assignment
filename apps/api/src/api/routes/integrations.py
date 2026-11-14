from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from src.integrations.foundry import check_foundry_connection
from src.integrations.x_api import connection_status, finish_oauth, start_oauth
from src.schemas.health import IntegrationStatus
from src.schemas.x_integration import XConnectionStatus

router = APIRouter()


@router.post("/foundry/check", response_model=IntegrationStatus)
def check_foundry() -> IntegrationStatus:
    return check_foundry_connection()


@router.get("/x/status", response_model=XConnectionStatus)
def x_status() -> dict:
    return connection_status()


@router.get("/x/connect")
def connect_x():
    return start_oauth()


@router.get("/x/callback")
def x_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail="X authorization was not completed.")
    if not code or not state:
        raise HTTPException(status_code=400, detail="X callback is missing authorization parameters.")
    return finish_oauth(code, state)
