import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from src.core.config import settings
from src.services.storage import database_client, database_operation

OAUTH_AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
OAUTH_TOKEN_URL = "https://api.x.com/2/oauth2/token"


def _fernet() -> Fernet:
    key = settings.x_token_encryption_key.get_secret_value() if settings.x_token_encryption_key else ""
    if not key and settings.supabase_server_key:
        key = base64.urlsafe_b64encode(
            hashlib.sha256(f"genai-fund:x-token-encryption:{settings.supabase_server_key}".encode()).digest()
        ).decode()
    try:
        return Fernet(key.encode())
    except Exception:
        raise HTTPException(status_code=503, detail="X token encryption is not configured. Set X_TOKEN_ENCRYPTION_KEY.") from None


def _configured_for_oauth() -> None:
    if not settings.x_client_id or not settings.x_client_secret or not settings.x_redirect_uri:
        raise HTTPException(status_code=503, detail="X OAuth client ID, client secret, and redirect URI are required.")
    _fernet()


def _encrypt(value: str | None) -> str | None:
    return _fernet().encrypt(value.encode()).decode() if value else None


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        raise HTTPException(status_code=503, detail="Stored X credentials cannot be decrypted. Check X_TOKEN_ENCRYPTION_KEY.") from None


def _saved_connection() -> dict | None:
    client = database_client()
    rows = database_operation(
        lambda: client.table("x_connections")
        .select("x_user_id,username,access_token_encrypted,refresh_token_encrypted,expires_at,scopes")
        .eq("id", True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _save_connection(payload: dict) -> dict:
    client = database_client()
    encrypted = {
        **payload,
        "id": True,
        "access_token_encrypted": _encrypt(payload["access_token"]),
        "refresh_token_encrypted": _encrypt(payload.get("refresh_token")),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 7200)))).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    encrypted.pop("access_token")
    encrypted.pop("refresh_token", None)
    encrypted.pop("expires_in", None)
    database_operation(lambda: client.table("x_connections").upsert(encrypted, on_conflict="id").execute())
    return _saved_connection() or {}


def _token_request(data: dict) -> dict:
    if not settings.x_client_id or not settings.x_client_secret:
        raise HTTPException(status_code=503, detail="X OAuth client credentials are not configured.")
    client_secret = settings.x_client_secret.get_secret_value()
    auth = base64.b64encode(f"{settings.x_client_id}:{client_secret}".encode()).decode()
    try:
        response = httpx.post(
            OAUTH_TOKEN_URL,
            data=data,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        if error.response.status_code in (400, 401):
            raise HTTPException(status_code=400, detail="X rejected OAuth credentials or authorization code.") from None
        raise HTTPException(status_code=502, detail=f"X OAuth returned HTTP {error.response.status_code}.") from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach X OAuth.") from None


def start_oauth() -> RedirectResponse:
    _configured_for_oauth()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    client = database_client()
    database_operation(lambda: client.table("x_oauth_states").insert({
        "state_hash": hashlib.sha256(state.encode()).hexdigest(),
        "code_verifier": verifier,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }).execute())
    query = urlencode({
        "response_type": "code",
        "client_id": settings.x_client_id,
        "redirect_uri": settings.x_redirect_uri,
        "scope": settings.x_oauth_scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"{OAUTH_AUTHORIZE_URL}?{query}", status_code=302)


def finish_oauth(code: str, state: str) -> RedirectResponse:
    _configured_for_oauth()
    client = database_client()
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    rows = database_operation(
        lambda: client.table("x_oauth_states")
        .select("state_hash,code_verifier,expires_at")
        .eq("state_hash", state_hash)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=400, detail="X OAuth state is invalid or expired.")
    oauth_state = rows[0]
    database_operation(lambda: client.table("x_oauth_states").delete().eq("state_hash", state_hash).execute())
    if datetime.fromisoformat(oauth_state["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="X OAuth state expired. Start the connection again.")

    token = _token_request({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.x_redirect_uri,
        "code_verifier": oauth_state["code_verifier"],
        "client_id": settings.x_client_id,
    })
    profile = _x_request("GET", "/users/me", token=token["access_token"], params={"user.fields": "name,username"})
    user = profile.get("data", {})
    if not user.get("id") or not user.get("username"):
        raise HTTPException(status_code=502, detail="X did not return the connected account profile.")
    _save_connection({
        "x_user_id": user["id"],
        "username": user["username"],
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
        "expires_in": token.get("expires_in", 7200),
        "scopes": token.get("scope", "").split(),
    })
    frontend = next(
        (origin for origin in settings.cors_origins if "127.0.0.1" in origin),
        settings.cors_origins[0] if settings.cors_origins else "http://127.0.0.1:5173",
    )
    return RedirectResponse(f"{frontend}/?x_connected=1", status_code=303)


def _refresh_connection(connection: dict) -> dict:
    refresh_token = _decrypt(connection.get("refresh_token_encrypted"))
    if not refresh_token:
        return connection
    expires_at = connection.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at.replace("Z", "+00:00")) > datetime.now(timezone.utc) + timedelta(minutes=2):
        return connection
    token = _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": settings.x_client_id})
    return _save_connection({
        "x_user_id": connection["x_user_id"],
        "username": connection["username"],
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token", refresh_token),
        "expires_in": token.get("expires_in", 7200),
        "scopes": token.get("scope", connection.get("scopes", [])),
    })


def _x_request(method: str, path: str, *, token: str | None = None, params=None, json=None) -> dict:
    access_token = token or current_access_token()
    try:
        response = httpx.request(
            method,
            f"{settings.x_api_base_url.rstrip('/')}{path}",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            params=params,
            json=json,
            timeout=httpx.Timeout(20.0, connect=5.0),
        )
        response.raise_for_status()
        return response.json() if response.content else {}
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status == 401:
            raise HTTPException(status_code=401, detail="X authorization expired or is invalid. Reconnect the account.") from None
        if status == 403:
            raise HTTPException(
                status_code=403,
                detail=f"X denied {method.upper()} {path}. Check OAuth scopes and whether this endpoint is enabled for the X project/access tier.",
            ) from None
        if status == 402:
            raise HTTPException(
                status_code=402,
                detail="X API credits are missing or depleted. Add credits in the X Developer Console, then retry discovery.",
            ) from None
        if status == 429:
            reset = error.response.headers.get("x-rate-limit-reset")
            detail = "X rate limit reached."
            if reset and reset.isdigit():
                detail += f" Try again after {datetime.fromtimestamp(int(reset), timezone.utc).isoformat()}."
            raise HTTPException(status_code=429, detail=detail) from None
        response_body = error.response.text.lower()
        if status == 400 and "duplicate" in response_body:
            raise HTTPException(status_code=409, detail="X reports this action as a duplicate.") from None
        if status == 400:
            try:
                payload = error.response.json()
                details = [item.get("message", "") for item in payload.get("errors", [])]
                detail = "; ".join(message for message in details if message)
            except (ValueError, TypeError):
                detail = ""
            if detail:
                raise HTTPException(status_code=400, detail=f"X rejected the request: {detail}") from None
            raise HTTPException(status_code=400, detail="X rejected this request. Check the search query, recipient eligibility, or message content.") from None
        raise HTTPException(status_code=502, detail=f"X API returned HTTP {status}.") from None
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="X API request timed out.") from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not connect to X API.") from None


def current_access_token() -> str:
    connection = _saved_connection()
    if connection:
        connection = _refresh_connection(connection)
        token = _decrypt(connection.get("access_token_encrypted"))
        if token:
            return token
    token = settings.x_access_token.get_secret_value().strip() if settings.x_access_token else ""
    if token:
        return token
    raise HTTPException(status_code=503, detail="Connect an X account before using X API features.")


def connected_user() -> dict:
    connection = _saved_connection()
    if connection:
        _refresh_connection(connection)
    data = _x_request("GET", "/users/me", params={"user.fields": "name,username"}).get("data", {})
    return {"id": data.get("id"), "username": data.get("username"), "name": data.get("name")}


def connection_status() -> dict:
    try:
        profile = connected_user()
        return {"status": "connected", "username": profile.get("username"), "message": "X account is connected."}
    except HTTPException as error:
        if error.status_code == 503:
            configured = bool(settings.x_client_id and settings.x_client_secret and settings.x_redirect_uri and settings.supabase_server_key)
            return {"status": "not_configured" if configured else "needs_setup", "username": None, "message": error.detail}
        return {"status": "error", "username": None, "message": error.detail}


def api_request(method: str, path: str, *, params=None, json=None) -> dict:
    connection = _saved_connection()
    if connection:
        _refresh_connection(connection)
    return _x_request(method, path, params=params, json=json)


def current_user_id() -> str:
    connection = _saved_connection()
    if connection:
        _refresh_connection(connection)
        return connection["x_user_id"]
    profile = connected_user()
    return profile["id"]
