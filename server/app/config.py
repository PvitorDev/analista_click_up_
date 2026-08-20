from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_ROOT / ".env", ".env"), extra="ignore")

    env: str = "development"
    database_url: str = "postgresql://clickup:clickup@localhost:5432/clickup_analyst"
    redis_url: str = "redis://localhost:6379"

    clickup_api_token: str = ""
    clickup_team_id: str = ""
    clickup_field_priority: str = "Prioridade"
    clickup_field_context: str = "Contexto"
    sync_interval_seconds: int = 300

    clickup_client_id: str = ""
    clickup_client_secret: str = ""
    clickup_redirect_uri: str = "http://localhost:8000/auth/callback"
    session_ttl_hours: int = 8
    session_cookie_name: str = "analyst_session"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    dev_bypass_auth: bool = False
    extract_refine_llm: bool = False

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_boot(self) -> None:
        if self.is_production and self.dev_bypass_auth:
            raise RuntimeError(
                "DEV_BYPASS_AUTH não pode estar ligado quando ENV=production."
            )


settings = Settings()
