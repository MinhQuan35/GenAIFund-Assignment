import httpx

from src.core.config import settings
from src.schemas.health import IntegrationStatus


class FoundryIntegrationError(Exception):
    pass


def foundry_configuration_status() -> IntegrationStatus:
    if not settings.foundry_is_configured:
        return IntegrationStatus(status="not_configured", message="Foundry credentials are incomplete.")
    return IntegrationStatus(status="configured", message="Foundry deployment is configured.")


def _request_text(prompt: str, max_output_tokens: int) -> str:
    if not settings.foundry_is_configured:
        raise FoundryIntegrationError("Foundry credentials are incomplete.")

    try:
        response = httpx.post(
            f"{settings.azure_openai_base_url.rstrip('/')}/responses",
            headers={
                "api-key": settings.azure_openai_api_key.get_secret_value(),
                "Content-Type": "application/json",
            },
            json={
                "model": settings.azure_openai_deployment_name,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
            },
            timeout=httpx.Timeout(20.0, connect=5.0),
        )
        response.raise_for_status()
        payload = response.json()
        has_text = any(
            content.get("type") == "output_text" and content.get("text", "").strip()
            for item in payload.get("output", [])
            for content in item.get("content", [])
        )
        if not has_text:
            raise FoundryIntegrationError("Foundry returned an empty response.")
        return "\n".join(
            content["text"].strip()
            for item in payload.get("output", [])
            for content in item.get("content", [])
            if content.get("type") == "output_text" and content.get("text", "").strip()
        ).strip()
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        if status_code == 401:
            message = "Foundry authentication failed. Check the API key."
        elif status_code == 403:
            message = "Foundry denied access to this deployment."
        elif status_code == 404:
            message = "Foundry could not find the configured endpoint or deployment."
        elif status_code == 429:
            message = "Foundry rate limit or quota was reached."
        else:
            message = f"Foundry returned HTTP {status_code}."
        raise FoundryIntegrationError(message) from None
    except httpx.TimeoutException:
        raise FoundryIntegrationError("Foundry request timed out.") from None
    except httpx.HTTPError:
        raise FoundryIntegrationError("Could not connect to the Foundry endpoint.") from None
    except (ValueError, KeyError, TypeError):
        raise FoundryIntegrationError("Foundry returned an invalid response.") from None
    except Exception:
        raise FoundryIntegrationError("Foundry check failed due to an unexpected error.") from None


def generate_text(prompt: str, max_output_tokens: int = 180) -> str:
    return _request_text(prompt, max_output_tokens)


def check_foundry_connection() -> IntegrationStatus:
    if not settings.foundry_is_configured:
        return foundry_configuration_status()
    try:
        _request_text("Reply with OK.", max_output_tokens=16)
        return IntegrationStatus(status="connected", message="Foundry deployment responded successfully.")
    except FoundryIntegrationError as error:
        return IntegrationStatus(status="error", message=str(error))
