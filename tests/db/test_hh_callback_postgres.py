import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.auth_session import UserSession
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHAPIClient, HHOAuthClient
from job_aggregator.schemas.hh_token import HHAccountTokenData
from job_aggregator.services.auth_sessions import AuthSessionService


@pytest.fixture
async def callback_pg(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """Callback на отдельной PostgreSQL; внешние запросы HH замоканы."""

    async def database() -> AsyncIterator[AsyncSession]:
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[get_settings] = lambda: Settings(
        hh_client_id="test-client",
        hh_client_secret="test-secret",
        hh_redirect_uri="https://example.test/api/auth/hh/callback",
        _env_file=None,
    )
    monkeypatch.setattr(
        HHAPIClient,
        "request",
        AsyncMock(return_value={"id": "hh-42", "first_name": "Иван"}),
    )
    monkeypatch.setattr(
        HHOAuthClient,
        "exchange_code",
        AsyncMock(
            return_value=HHAccountTokenData(
                access_token="test-access",
                refresh_token="test-refresh",
                access_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
        ),
    )
    async with pg_session_factory() as session:
        state = await AuthSessionService(session).create_oauth_state()
        await session.commit()
        return state


async def test_concurrent_callbacks_only_exchange_once(
    async_client: AsyncClient,
    callback_pg: str,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                async_client.get(
                    "/auth/hh/callback",
                    params={"code": "test-code", "state": callback_pg},
                )
                for _ in range(2)
            )
        ),
        timeout=10,
    )
    assert sorted(response.status_code for response in responses) == [303, 400]
    HHOAuthClient.exchange_code.assert_awaited_once()
    async with pg_session_factory() as session:
        for model in (User, HHAccount, UserSession):
            assert await session.scalar(select(func.count()).select_from(model)) == 1


async def test_failed_login_commit_is_atomic_on_postgres(
    async_client: AsyncClient,
    callback_pg: str,
    pg_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AsyncSession.commit
    calls = 0

    async def failing_commit(session: AsyncSession) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("private-database-details")
        await original(session)

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "test-code", "state": callback_pg}
    )
    assert response.status_code == 500
    assert "set-cookie" not in response.headers
    async with pg_session_factory() as session:
        for model in (User, UserSettings, HHAccount, UserSession):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
        assert (
            await AuthSessionService(session).consume_oauth_state(callback_pg) is False
        )
