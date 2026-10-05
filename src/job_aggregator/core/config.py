from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "job-aggregator"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/job_aggregator"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
