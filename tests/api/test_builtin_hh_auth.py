from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

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


async def test_builtin_start_uses_sdk_defaults(async_client: AsyncClient, builtin_auth):
    response = await async_client.post("/auth/hh/start")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "mobile"
    url = urlsplit(data["authorization_url"])
    assert url.hostname == "hh.ru"
    query = parse_qs(url.query)
    assert query["client_id"][0]
    assert "redirect_uri" not in query
    assert query["state"][0]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "no-store" in response.headers["cache-control"]


async def test_builtin_completion_requires_browser_state(
    async_client: AsyncClient, builtin_auth
):
    response = await async_client.post(
        "/auth/hh/complete",
        json={
            "return_url": "hhandroid://oauthresponse?code=private-code&state=forged",
        },
    )
    assert response.status_code == 400
    assert "private-code" not in response.text


async def test_builtin_completion_creates_session(
    async_client: AsyncClient, builtin_auth, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    from job_aggregator.integrations.hh.client import HHAPIClient, HHOAuthClient
    from job_aggregator.integrations.hh.dto import HHUserProfile
    from job_aggregator.schemas.hh_token import HHAccountTokenData

    monkeypatch.setattr(
        HHOAuthClient,
        "exchange_code",
        AsyncMock(
            return_value=HHAccountTokenData(
                access_token="private-access",
                refresh_token="private-refresh",
                access_expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        ),
    )
    monkeypatch.setattr(
        HHAPIClient,
        "get_current_user",
        AsyncMock(
            return_value=HHUserProfile(
                hh_user_id="123",
                display_name="Иван",
            )
        ),
    )
    start = await async_client.post("/auth/hh/start")
    state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
    payload = {
        "return_url": f"hhandroid://oauthresponse?code=private-code&state={state}"
    }
    response = await async_client.post("/auth/hh/complete", json=payload)
    assert response.status_code == 204
    assert "job_aggregator_session=" in response.headers["set-cookie"]
    assert "httponly" in response.headers["set-cookie"].lower()
    HHOAuthClient.exchange_code.assert_awaited_once_with("private-code", "")
    profile = await async_client.get("/me")
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Иван"
    assert profile.json()["new_matches_count"] is None
    assert "private-" not in profile.text
    async_client.cookies.set("hh_oauth_state", state)
    assert (
        await async_client.post("/auth/hh/complete", json=payload)
    ).status_code == 400
    assert (await async_client.post("/auth/logout")).status_code == 204
    assert (await async_client.get("/me")).status_code == 401


@pytest.mark.parametrize("path,method", [("/me", "GET"), ("/me/settings", "PATCH")])
async def test_profile_requires_session(async_client, builtin_auth, path, method):
    response = await async_client.request(
        method, path, json={} if method == "PATCH" else None
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "return_url",
    [
        "https://evil.test/?code=secret&state=secret",
        "hhandroid://oauthresponse?code=secret",
        "hhandroid://oauthresponse?code=secret&code=second&state=secret",
        "hhandroid://oauthresponse?code=secret&state=secret#fragment",
        "hhandroid://other?code=secret&state=secret",
        "hhandroid://[invalid",
    ],
)
async def test_invalid_return_urls_do_not_leak_code(
    async_client, builtin_auth, return_url
):
    start = await async_client.post("/auth/hh/start")
    state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
    return_url = return_url.replace("state=secret", f"state={state}")
    response = await async_client.post(
        "/auth/hh/complete", json={"return_url": return_url}
    )
    assert response.status_code == 400
    assert "secret" not in response.text


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
