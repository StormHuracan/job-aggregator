import pytest
from httpx import AsyncClient, ASGITransport
from collections.abc import AsyncIterator, Iterator
from datetime import UTC
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from job_aggregator.api.router import api_router
from job_aggregator.main import create_app

@pytest.fixture
def app():
    test_app = create_app()
    yield test_app
    test_app.dependency_overrides.clear()

@pytest.fixture
def client() -> Iterator[TestClient]:
    """Выдаёт клиент настоящих роутеров без production lifespan.

    Зависимости подменяются через client.app.dependency_overrides. Каждый тест
    получает отдельное приложение. Запуск production-приложения эта fixture
    не проверяет. Для API-тестов без БД необходимо подменить зависимости сервисов.
    """
    # Production lifespan подключается к БД независимо от dependency_overrides.
    app = FastAPI()
    app.include_router(api_router)

    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app)
    async with  AsyncClient(transport=transport, base_url= "http://test") as client:
        yield client




@pytest.fixture
async def sqlite_session() -> AsyncIterator[AsyncSession]:
    """Выдаёт чистую SQLite-сессию; PostgreSQL-specific поведение не проверяет.

    Схема создаётся по ORM-моделям, а не миграциями. Восстановление UTC для токенов
    компенсирует потерю timezone в SQLite только в рамках этой сессии.
    """
    from job_aggregator.db.base import Base
    from job_aggregator.db.models import saved_search, vacancy  # noqa: F401
    from job_aggregator.db.models.hh_account_token import HHAccountToken
    from job_aggregator.db.session import create_engine_and_factory

    def restore_token_timezone(session: Session, instance: object) -> None:
        if isinstance(instance, HHAccountToken):
            value = instance.access_expires_at
            if value is not None and value.tzinfo is None:
                instance.access_expires_at = value.replace(tzinfo=UTC)

    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            event.listen(
                session.sync_session, "loaded_as_persistent", restore_token_timezone
            )
            try:
                yield session
            finally:
                event.remove(
                    session.sync_session, "loaded_as_persistent", restore_token_timezone
                )
    finally:
        await engine.dispose()
