from collections.abc import AsyncIterator
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.auth_session import OAuthState, UserSession
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService


@pytest.fixture
def login_dependencies(
    app: FastAPI, sqlite_session: AsyncSession
) -> async_sessionmaker[AsyncSession]:
    """Проверяет commit через отдельные сессии на общей тестовой БД."""
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        hh_client_id="test-client",
        hh_client_secret="test-secret",
        hh_redirect_uri="https://example.com/auth/hh/callback",
        _env_file=None,
    )
    return factory


async def test_login_commits_unique_state_before_redirect(
    async_client: AsyncClient,
    login_dependencies: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    states: list[str] = []
    for _ in range(2):
        response = await async_client.get("/auth/hh/login", follow_redirects=False)
        assert response.status_code == 307
        location = urlparse(response.headers["location"])
        assert location.scheme == "https"
        assert location.hostname == "hh.ru"
        query = parse_qs(location.query)
        assert query["client_id"] == ["test-client"]
        assert query["redirect_uri"] == ["https://example.com/auth/hh/callback"]
        states.append(query["state"][0])
        assert "set-cookie" not in response.headers
        assert "test-secret" not in response.headers["location"]
        assert "test-secret" not in response.text
        assert states[-1] not in response.text

    assert states[0] != states[1]
    async with login_dependencies() as session:
        records = list(await session.scalars(select(OAuthState)))
        assert {record.state_hash for record in records} == {
            sha256(state.encode()).hexdigest() for state in states
        }
        assert all(record.state_hash not in states for record in records)
        for model in (User, HHAccount, UserSession):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
        service = AuthSessionService(session)
        assert await service.consume_oauth_state(states[0]) is True
        await session.commit()

    async with login_dependencies() as session:
        assert await AuthSessionService(session).consume_oauth_state(states[0]) is False

    assert "test-secret" not in caplog.text
    assert all(state not in caplog.text for state in states)


@pytest.mark.parametrize(
    "missing", ["hh_client_id", "hh_client_secret", "hh_redirect_uri"]
)
async def test_missing_settings_use_sdk_defaults(
    app: FastAPI,
    async_client: AsyncClient,
    login_dependencies: async_sessionmaker[AsyncSession],
    missing: str,
) -> None:
    values = {
        "hh_client_id": "test-client",
        "hh_client_secret": "test-secret",
        "hh_redirect_uri": "https://example.com/auth/hh/callback",
    }
    values[missing] = None
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, **values)

    response = await async_client.get("/auth/hh/login", follow_redirects=False)

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["client_id"][0]
    assert ("redirect_uri" in query) == (missing != "hh_redirect_uri")
    assert "test-secret" not in response.text
    async with login_dependencies() as session:
        assert await session.scalar(select(func.count()).select_from(OAuthState)) == 1
