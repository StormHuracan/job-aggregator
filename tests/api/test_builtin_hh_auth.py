from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.session import get_db_session


@pytest.fixture
def builtin_auth(app: FastAPI, sqlite_session: AsyncSession):
    """Подключает реальные сервисы к общей SQLite fixture без OAuth-настроек."""

    async def db():
        yield sqlite_session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)


@pytest.mark.parametrize("path,method", [("/me", "GET"), ("/me/settings", "PATCH")])
async def test_profile_requires_session(async_client, builtin_auth, path, method):
    response = await async_client.request(
        method, path, json={} if method == "PATCH" else None
    )
    assert response.status_code == 401


async def test_settings_partial_update_and_owner_isolation(
    async_client, builtin_auth, sqlite_session
):
    from job_aggregator.db.repositories.user import (
        UserRepository,
        UserSettingsRepository,
    )
    from job_aggregator.services.auth_sessions import AuthSessionService

    user = await UserRepository(sqlite_session).get_or_create("first", "Первый")
    other = await UserRepository(sqlite_session).get_or_create("second", "Второй")
    token = await AuthSessionService(sqlite_session).create_session(user.id)
    await sqlite_session.commit()
    async_client.cookies.set("job_aggregator_session", token)
    response = await async_client.patch(
        "/me/settings", json={"default_area": "  Москва  "}
    )
    assert response.status_code == 200
    assert response.json() == {"default_area": "Москва", "default_pages_limit": 5}
    assert (
        await async_client.patch("/me/settings", json={"default_area": None})
    ).json()["default_area"] is None
    for payload in (
        {"default_pages_limit": None},
        {"default_pages_limit": 0},
        {"user_id": other.id},
    ):
        assert (
            await async_client.patch("/me/settings", json=payload)
        ).status_code == 422
    assert (await async_client.get("/me")).json()["settings"][
        "default_pages_limit"
    ] == 5
    other_settings = await UserSettingsRepository(sqlite_session).get_or_create(
        other.id
    )
    assert other_settings.default_area is None


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/me"),
        ("PATCH", "/me/settings"),
        ("POST", "/auth/logout"),
    ],
)
async def test_commit_failure_is_safe(
    async_client,
    builtin_auth,
    sqlite_session,
    monkeypatch,
    method,
    path,
):
    from sqlalchemy.exc import SQLAlchemyError

    from job_aggregator.db.repositories.user import UserRepository
    from job_aggregator.services.auth_sessions import AuthSessionService

    user = await UserRepository(sqlite_session).get_or_create("owner", "Owner")
    token = await AuthSessionService(sqlite_session).create_session(user.id)
    await sqlite_session.commit()
    async_client.cookies.set("job_aggregator_session", token)
    monkeypatch.setattr(
        sqlite_session, "commit", AsyncMock(side_effect=SQLAlchemyError("private-sql"))
    )
    response = await async_client.request(
        method, path, json={"default_area": "Москва"} if method == "PATCH" else None
    )
    assert response.status_code == 500
    assert "private-sql" not in response.text
    assert "job_aggregator_session" not in response.headers.get("set-cookie", "")
