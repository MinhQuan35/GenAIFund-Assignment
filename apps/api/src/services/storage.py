from fastapi import HTTPException
from supabase import Client

from src.integrations.supabase import get_supabase_client


def database_client() -> Client:
    try:
        client = get_supabase_client()
    except Exception:
        raise HTTPException(status_code=503, detail="Supabase client is unavailable.") from None
    if client is None:
        raise HTTPException(status_code=503, detail="Supabase server credentials are not configured.")
    return client


def database_operation(operation):
    try:
        return operation()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Supabase operation failed.") from None
