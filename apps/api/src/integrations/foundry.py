import httpx

from src.core.config import settings
from src.schemas.health import IntegrationStatus


class FoundryIntegrationError(Exception):
    pass


def foundry_configuration_status() -> IntegrationStatus:
    provider = settings.llm_provider.casefold()
    if not settings.llm_is_configured:
        return IntegrationStatus(status="not_configured", message=f"{provider} model credentials are incomplete.")
    return IntegrationStatus(status="configured", message=f"{provider} model is configured.")


def _request_text(prompt: str, max_output_tokens: int) -> str:
    provider = settings.llm_provider.casefold()
    if not settings.llm_is_configured:
        raise FoundryIntegrationError(f"{provider} model credentials are incomplete.")

    if provider == "openai":
        base_url = settings.openai_base_url
        model = settings.openai_model
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
    elif provider == "foundry":
        base_url = settings.azure_openai_base_url
        model = settings.azure_openai_deployment_name
        headers = {
            "api-key": settings.azure_openai_api_key.get_secret_value(),
            "Content-Type": "application/json",
        }
    else:
        raise FoundryIntegrationError("LLM_PROVIDER must be either 'foundry' or 'openai'.")

    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/responses",
            headers=headers,
            json={
                "model": model,
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
            message = f"{provider} authentication failed. Check the API key."
        elif status_code == 403:
            message = f"{provider} denied access to this model."
        elif status_code == 404:
            message = f"{provider} could not find the configured endpoint or model."
        elif status_code == 429:
            message = f"{provider} rate limit or quota was reached."
        else:
            message = f"Foundry returned HTTP {status_code}."
        raise FoundryIntegrationError(message) from None
    except httpx.TimeoutException:
        raise FoundryIntegrationError("Foundry request timed out.") from None
    except httpx.HTTPError:
        raise FoundryIntegrationError(f"Could not connect to the {provider} endpoint.") from None
    except (ValueError, KeyError, TypeError):
        raise FoundryIntegrationError("Foundry returned an invalid response.") from None
    except Exception:
        raise FoundryIntegrationError(f"{provider} check failed due to an unexpected error.") from None


def generate_text(prompt: str, max_output_tokens: int = 180) -> str:
    return _request_text(prompt, max_output_tokens)


def check_foundry_connection() -> IntegrationStatus:
    if not settings.llm_is_configured:
        return foundry_configuration_status()
    try:
        _request_text("Reply with OK.", max_output_tokens=16)
        return IntegrationStatus(status="connected", message=f"{settings.llm_provider} model responded successfully.")
    except FoundryIntegrationError as error:
        return IntegrationStatus(status="error", message=str(error))
