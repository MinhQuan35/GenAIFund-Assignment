from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GenAI Fund Outreach API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    supabase_url: str | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    database_url: str | None = None
    direct_url: str | None = None
    azure_openai_base_url: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_deployment_name: str | None = None

    @property
    def supabase_server_key(self) -> str | None:
        for key in (self.supabase_secret_key, self.supabase_service_role_key):
            if key and key.get_secret_value().strip():
                return key.get_secret_value().strip()
        return None

    @property
    def foundry_is_configured(self) -> bool:
        return all(
            value and value.strip()
            for value in (
                self.azure_openai_base_url,
                self.azure_openai_deployment_name,
                self.azure_openai_api_key.get_secret_value() if self.azure_openai_api_key else None,
            )
        )


settings = Settings()
