from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.session import create_engine_and_factory, get_db_session


async def test_database_errors_hide_secret_parameters() -> None:
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    try:
        async with factory() as session:
            with pytest.raises(DBAPIError) as error:
                await session.execute(
                    text("INSERT INTO missing_token_table VALUES (:token)"),
                    {"token": "secret-access-value"},
                )
            assert "secret-access-value" not in str(error.value)
    finally:
        await engine.dispose()


async def test_session_factory_yields_working_session() -> None:
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    try:
        async with factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()


def test_dependency_provides_working_session() -> None:
    """Dependency выдаёт рабочую AsyncSession на время запроса."""
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")

    test_app = FastAPI()
    test_app.state.session_factory = factory

    @test_app.get("/probe")
    async def probe(
        session: AsyncSession = Depends(get_db_session),
    ) -> dict[str, bool]:
        await session.execute(text("SELECT 1"))
        return {"ok": True}

    with TestClient(test_app) as client:
        response = client.get("/probe")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


def _build_app_with_mocked_session() -> tuple[FastAPI, AsyncMock]:
    """Собирает приложение, где session_factory — мок, а сессия — AsyncMock."""
    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=fake_session)

    test_app = FastAPI()
    test_app.state.session_factory = factory
    return test_app, fake_session


def test_dependency_closes_session_after_request() -> None:
    """После успешного запроса сессия закрывается (__aexit__ вызван)."""
    test_app, fake_session = _build_app_with_mocked_session()

    @test_app.get("/probe")
    async def probe(
        session: AsyncSession = Depends(get_db_session),
    ) -> dict[str, bool]:
        return {"ok": True}

    with TestClient(test_app) as client:
        response = client.get("/probe")
        assert response.status_code == 200

    fake_session.__aexit__.assert_awaited_once()


def test_dependency_closes_session_on_error() -> None:
    """Сессия закрывается и в ошибочном сценарии (5xx)."""
    test_app, fake_session = _build_app_with_mocked_session()

    @test_app.get("/boom")
    async def boom(
        session: AsyncSession = Depends(get_db_session),
    ) -> dict[str, bool]:
        raise RuntimeError("boom")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
        assert response.status_code == 500

    fake_session.__aexit__.assert_awaited_once()
