from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from job_aggregator.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Изолирует тесты от .env, переменных окружения и кэша настроек."""
    monkeypatch.chdir(tmp_path)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.hh_client_id is None
    assert settings.hh_client_secret is None
    assert settings.hh_redirect_uri is None
    assert settings.hh_allow_token_refresh is False
    assert settings.scheduler_enabled is False
    assert settings.scheduler_interval_minutes == 60
    assert settings.app_name == "job-aggregator"


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "my-app")
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("HH_ALLOW_TOKEN_REFRESH", "true")
    monkeypatch.setenv("SCHEDULER_INTERVAL_MINUTES", "30")

    settings = Settings()

    assert settings.app_name == "my-app"
    assert settings.scheduler_enabled is True
    assert settings.hh_allow_token_refresh is True
    assert settings.scheduler_interval_minutes == 30


def test_pages_limit_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_PAGES_LIMIT", "0")

    with pytest.raises(ValidationError):
        Settings()


def test_scheduler_interval_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_INTERVAL_MINUTES", "-1")

    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_is_cached() -> None:
    first = get_settings()
    second = get_settings()

    assert first is second


def test_empty_env_value_is_treated_as_missing(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "HH_CLIENT_ID=\nAPP_NAME=from-dotenv\n", encoding="utf-8"
    )

    settings = Settings()

    assert settings.hh_client_id is None
    assert settings.app_name == "from-dotenv"
