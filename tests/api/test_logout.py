from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from job_aggregator.db.models.auth_session import UserSession
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService
from tests.factories import make_token_data


@pytest.fixture
async def logout_api(app, sqlite_session):
    """Настоящие сессии на общей тестовой БД без запросов к HH."""
    app.dependency_overrides[get_db_session] = lambda: sqlite_session
    service = AuthSessionService(sqlite_session)
    owner = await UserRepository(sqlite_session).get_or_create("hh-one", "Первый")
    other = await UserRepository(sqlite_session).get_or_create("hh-two", "Второй")
    current = await service.create_session(owner.id)
    second = await service.create_session(owner.id)
    foreign = await service.create_session(other.id)
    await HHAccountRepository(sqlite_session).save(owner.id, make_token_data())
    await sqlite_session.commit()
    return current, second, foreign


@pytest.mark.parametrize("token", [None, "unknown-token"])
async def test_logout_requires_valid_session(async_client, logout_api, token):
    if token:
        async_client.cookies.set("job_aggregator_session", token)
    response = await async_client.post("/auth/logout")
    assert response.status_code == 401


async def test_logout_revokes_only_current_session_and_preserves_hh(
    async_client, logout_api, sqlite_session
):
    current, second, foreign = logout_api
    async_client.cookies.set("job_aggregator_session", current)
    response = await async_client.post("/auth/logout")
    assert response.status_code == 204
    assert not response.content
    assert "Max-Age=0" in response.headers["set-cookie"]
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)
    async with factory() as check:
        service = AuthSessionService(check)
        assert await service.get_user_id(current) is None
        assert await service.get_user_id(second) is not None
        assert await service.get_user_id(foreign) is not None
        assert await check.scalar(select(func.count()).select_from(HHAccount)) == 1
    async_client.cookies.set("job_aggregator_session", current)
    assert (await async_client.post("/auth/logout")).status_code == 401


async def test_logout_does_not_rotate_session_near_expiry(
    async_client, logout_api, sqlite_session
):
    current, _, _ = logout_api
    await sqlite_session.execute(
        UserSession.__table__.update().values(
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
    )
    await sqlite_session.commit()
    async_client.cookies.set("job_aggregator_session", current)
    response = await async_client.post("/auth/logout")
    assert response.status_code == 204
    assert len(response.headers.get_list("set-cookie")) == 1
    assert (
        await sqlite_session.scalar(select(func.count()).select_from(UserSession)) == 3
    )


async def test_logout_expired_session_is_unauthorized(
    async_client, logout_api, sqlite_session
):
    current, _, _ = logout_api
    await sqlite_session.execute(
        UserSession.__table__.update().values(
            expires_at=datetime.now(UTC) - timedelta(minutes=1)
        )
    )
    await sqlite_session.commit()
    async_client.cookies.set("job_aggregator_session", current)
    assert (await async_client.post("/auth/logout")).status_code == 401


async def test_logout_failed_commit_keeps_session_valid(
    async_client, logout_api, sqlite_session, monkeypatch
):
    current, _, _ = logout_api
    async_client.cookies.set("job_aggregator_session", current)
    monkeypatch.setattr(
        sqlite_session, "commit", AsyncMock(side_effect=SQLAlchemyError("private-sql"))
    )
    response = await async_client.post("/auth/logout")
    assert response.status_code == 500
    assert "private-sql" not in response.text
    assert "set-cookie" not in response.headers
    assert await AuthSessionService(sqlite_session).get_user_id(current) is not None
