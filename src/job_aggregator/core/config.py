from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "job-aggregator"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_aggregator"

    hh_client_id: str | None = None
    hh_client_secret: str | None = None
    hh_redirect_uri: str | None = None

    collection_default_query: str = "Python developer"
    collection_default_area: str | None = None
    collection_pages_limit: int = 2

    scheduler_enabled: bool = False
    scheduler_interval_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
