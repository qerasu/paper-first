from functools import lru_cache
from json import JSONDecodeError, loads

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(value: str) -> list[str]:
    raw_value = value.strip()
    if not raw_value:
        return []

    if raw_value.startswith("["):
        try:
            parsed_value = loads(raw_value)
        except JSONDecodeError:
            raw_value = raw_value.strip("[]")
        else:
            if isinstance(parsed_value, list):
                return [str(origin).strip() for origin in parsed_value if str(origin).strip()]

    return [origin.strip().strip("\"'") for origin in raw_value.split(",") if origin.strip()]


def normalize_database_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)

    return value


class Settings(BaseSettings):
    app_name: str = "Paper First"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://paperfirst:paperfirst@localhost:5432/paperfirst"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str | None = None
    telegram_bot_username: str | None = None
    telegram_web_app_url: str = "http://localhost:5173"
    backend_cors_origins: str = "http://localhost:5173"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    model_config = SettingsConfigDict(
        env_prefix="PAPERFIRST_",
        env_file=None,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
