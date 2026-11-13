from functools import lru_cache

import httpx
from supabase import Client, create_client

from src.core.config import settings
from src.schemas.health import IntegrationStatus


def _credentials() -> tuple[str, str] | None:
    if not settings.supabase_url or not settings.supabase_server_key:
        return None
    return settings.supabase_url.rstrip("/"), settings.supabase_server_key


@lru_cache
def get_supabase_client() -> Client | None:
    credentials = _credentials()
    if credentials is None:
        return None
    url, key = credentials
    return create_client(url, key)


def check_supabase_connection() -> IntegrationStatus:
    credentials = _credentials()
    if credentials is None:
        return IntegrationStatus(status="not_configured", message="Supabase server credentials are incomplete.")

    url, key = credentials
    try:
        if get_supabase_client() is None:
            return IntegrationStatus(status="not_configured", message="Supabase server credentials are incomplete.")
        with httpx.stream(
            "GET",
            f"{url}/rest/v1/",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Accept": "application/openapi+json",
            },
            timeout=httpx.Timeout(5.0, connect=3.0),
        ) as response:
            response.raise_for_status()
        return IntegrationStatus(status="connected", message="Supabase REST API is reachable.")
    except httpx.TimeoutException:
        message = "Supabase health check timed out."
    except httpx.HTTPStatusError as error:
        message = f"Supabase returned HTTP {error.response.status_code}."
    except httpx.HTTPError:
        message = "Could not connect to Supabase."
    except Exception:
        message = "Supabase client could not be initialized."

    return IntegrationStatus(status="error", message=message)
