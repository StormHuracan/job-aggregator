from collections.abc import AsyncIterator, Iterator
from datetime import UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from job_aggregator.main import create_app


@pytest.fixture
def app() -> Iterator[FastAPI]:
    test_app = create_app()
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Выдаёт клиент настоящих роутеров без production lifespan.

    Зависимости подменяются через client.app.dependency_overrides. Каждый тест
    получает отдельное приложение. Запуск production-приложения эта fixture
    не проверяет. Для API-тестов без БД необходимо подменить зависимости сервисов.
    """
    # Production lifespan подключается к БД независимо от dependency_overrides.
    test_client = TestClient(app)
    yield test_client


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def sqlite_session() -> AsyncIterator[AsyncSession]:
    """Выдаёт чистую SQLite-сессию; PostgreSQL-specific поведение не проверяет.

    Схема создаётся по ORM-моделям, а не миграциями. Восстановление UTC для токенов
    компенсирует потерю timezone в SQLite только на время действия fixture,
    включая отдельные сессии сервисов на том же тестовом двигателе.
    """
    from job_aggregator.db.base import Base
    from job_aggregator.db.models import (  # noqa: F401
        auth_session,
        collection_progress,
        hh_account,
        saved_search,
        saved_search_match,
        user,
        vacancy,
    )
    from job_aggregator.db.models.hh_account import HHAccount
    from job_aggregator.db.models.hh_account_token import HHAccountToken
    from job_aggregator.db.session import create_engine_and_factory

    def restore_token_timezone(session: Session, instance: object) -> None:
        if isinstance(instance, (HHAccountToken, HHAccount)):
            value = instance.access_expires_at
            if value is not None and value.tzinfo is None:
                instance.access_expires_at = value.replace(tzinfo=UTC)

    def restore_refreshed_timezone(
        instance: HHAccount, context: object, attrs: object
    ) -> None:
        value = instance.access_expires_at
        if value is not None and value.tzinfo is None:
            instance.access_expires_at = value.replace(tzinfo=UTC)

    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            event.listen(Session, "loaded_as_persistent", restore_token_timezone)
            event.listen(HHAccount, "refresh", restore_refreshed_timezone)
            try:
                yield session
            finally:
                event.remove(Session, "loaded_as_persistent", restore_token_timezone)
                event.remove(HHAccount, "refresh", restore_refreshed_timezone)
    finally:
        await engine.dispose()
