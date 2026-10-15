import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.base import Base
from job_aggregator.db.models import (  # noqa: F401
    auth_session,
    hh_account_token,
    saved_search,
    user,
    vacancy,
)
from job_aggregator.db.session import create_engine_and_factory


def _test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def pg_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Фабрика async-сессий для реального PostgreSQL.

    Требует env var TEST_DATABASE_URL. Без неё тест скипается.
    Схема пересоздаётся перед прогоном — это отдельная тестовая БД,
    рабочую БД разработчика использовать нельзя.
    """
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set — PostgreSQL tests are skipped")

    engine, factory = create_engine_and_factory(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await engine.dispose()
