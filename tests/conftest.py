from collections.abc import Iterator
from datetime import UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event

from job_aggregator.api.router import api_router
from job_aggregator.db.models.hh_account_token import HHAccountToken


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Выдаёт клиент настоящих роутеров без production lifespan и БД.

    Зависимости подменяются через client.app.dependency_overrides. Каждый тест
    получает отдельное приложение. Запуск приложения и работу хранилища эта
    fixture не проверяет — для них нужны отдельные интеграционные тесты.
    """
    # Production lifespan подключается к БД независимо от dependency_overrides.
    app = FastAPI()
    app.include_router(api_router)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _sqlite_utc_datetimes():
    """SQLite теряет tz-info — восстанавливаем UTC при загрузке модели."""

    def _on_load(target, context):
        value = target.access_expires_at
        if value is not None and value.tzinfo is None:
            target.access_expires_at = value.replace(tzinfo=UTC)

    event.listen(HHAccountToken, "load", _on_load, propagate=True)
    yield
    event.remove(HHAccountToken, "load", _on_load)
