import sys
from functools import lru_cache
from typing import Annotated

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(min_length=1)
    anthropic_api_key: str = Field(min_length=1)
    database_url: str = Field(min_length=1)
    allowed_user_ids: Annotated[frozenset[int], NoDecode] = Field(min_length=1)

    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "medium"
    default_tz: str = "Europe/Moscow"
    log_level: str = "INFO"
    ask_daily_limit: int = 30

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_user_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(int(part) for part in value.split(",") if part.strip())
        if isinstance(value, int):
            return frozenset({value})
        return value

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Railway выдаёт postgresql://..., для SQLAlchemy async нужен драйвер asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value.removeprefix(prefix)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def load_settings() -> Settings:
    """Загружает настройки; при ошибке завершает процесс с понятным сообщением без секретов."""
    try:
        return get_settings()
    except ValidationError as exc:
        names = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err["loc"]})
        sys.exit(
            "Ошибка конфигурации: не заданы или некорректны переменные окружения: "
            + ", ".join(names)
        )
