from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Настройки конфигурации через переменные окружения.
    Значения читаются из переменных окружения и файла .env.
    Переменные окружения имеют приоритет над .env.
    """

    app_name: str = "job-aggregator"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/job_aggregator"
    )

    hh_client_id: str | None = None
    hh_client_secret: str | None = None
    hh_redirect_uri: str | None = None
    hh_allow_token_refresh: bool = False

    collection_default_query: str = "python"
    collection_default_area: str | None = None
    collection_pages_limit: int = Field(default=5, gt=0)

    scheduler_enabled: bool = False
    scheduler_interval_minutes: int = Field(default=60, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Возвращает настройки конфигурации.
    Результат кэшируется:
    возвращается тот же объект, настройки не перечитываются.
    """

    return Settings()
