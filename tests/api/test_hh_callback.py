from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.auth_session import OAuthState, UserSession
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHAPIClient, HHOAuthClient
from job_aggregator.schemas.hh_token import HHAccountTokenData
from job_aggregator.services.auth_sessions import AuthSessionService

TOKENS = HHAccountTokenData(
    access_token="private-access",
    refresh_token="private-refresh",
    access_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
)


@pytest.fixture
def callback_db(
    app: FastAPI, sqlite_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Реальные транзакции и ORM; только HTTP-граница HH подменяется."""
    engine = sqlite_session.bind

    def begin(connection) -> None:
        # Legacy SQLite не начинает транзакцию для SELECT/SAVEPOINT: без BEGIN
        # release savepoint мог бы сохранить User независимо от внешнего rollback.
        connection.exec_driver_sql("BEGIN")

    event.listen(engine.sync_engine, "begin", begin)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def database() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[get_settings] = lambda: Settings(
        hh_client_id="private-id",
        hh_client_secret="private-secret",
        hh_redirect_uri="https://example.test/api/auth/hh/callback",
        _env_file=None,
    )
    monkeypatch.setattr(
        HHAPIClient,
        "request",
        AsyncMock(return_value={"id": "hh-42", "first_name": "Иван"}),
    )
    monkeypatch.setattr(HHOAuthClient, "exchange_code", AsyncMock(return_value=TOKENS))
    try:
        yield factory
    finally:
        event.remove(engine.sync_engine, "begin", begin)


async def create_state(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as session:
        state = await AuthSessionService(session).create_oauth_state()
        await session.commit()
        return state


async def test_callback_commits_login_and_cookie(
    async_client: AsyncClient, callback_db, caplog: pytest.LogCaptureFixture
) -> None:
    state = await create_state(callback_db)
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/account"
    cookie = response.cookies.get("job_aggregator_session")
    assert cookie
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header
    assert "path=/" in header and "max-age=604800" in header
    assert "secure" not in header
    async with callback_db() as session:
        user = await session.scalar(select(User))
        assert user.hh_user_id == "hh-42"
        assert user.display_name == "Иван"
        assert await session.get(UserSettings, user.id) is not None
        account = await session.scalar(select(HHAccount))
        assert account.user_id == user.id
        assert account.access_token == TOKENS.access_token
        assert account.refresh_token == TOKENS.refresh_token
        assert await AuthSessionService(session).get_user_id(cookie) == user.id
    for secret in (
        TOKENS.access_token,
        TOKENS.refresh_token,
        "private-secret",
        "private-code",
        cookie,
        state,
    ):
        assert secret not in response.text
        assert secret not in response.headers["location"]
        assert secret not in caplog.text


async def test_state_is_committed_before_exchange(
    async_client: AsyncClient, callback_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = await create_state(callback_db)

    async def exchange(code: str, redirect_uri: str) -> HHAccountTokenData:
        assert code == "private-code"
        assert redirect_uri == "https://example.test/api/auth/hh/callback"
        async with callback_db() as session:
            assert await AuthSessionService(session).consume_oauth_state(state) is False
        return TOKENS

    monkeypatch.setattr(HHOAuthClient, "exchange_code", staticmethod(exchange))
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == 303


async def test_repeated_login_updates_same_account(
    async_client: AsyncClient, callback_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    for token in ("private-access", "replacement-access"):
        monkeypatch.setattr(
            HHOAuthClient,
            "exchange_code",
            AsyncMock(return_value=TOKENS.model_copy(update={"access_token": token})),
        )
        state = await create_state(callback_db)
        response = await async_client.get(
            "/auth/hh/callback", params={"code": "private-code", "state": state}
        )
        assert response.status_code == 303
    async with callback_db() as session:
        for model in (User, HHAccount, UserSettings):
            assert await session.scalar(select(func.count()).select_from(model)) == 1
        assert await session.scalar(select(func.count()).select_from(UserSession)) == 2
        assert (
            await session.scalar(select(HHAccount))
        ).access_token == "replacement-access"


@pytest.mark.parametrize("kind", ["missing", "expired", "consumed"])
async def test_invalid_state_never_exchanges_code(
    async_client: AsyncClient, callback_db, kind: str
) -> None:
    state = "unknown-state" if kind == "missing" else await create_state(callback_db)
    if kind != "missing":
        async with callback_db() as session:
            record = await session.scalar(
                select(OAuthState).where(
                    OAuthState.state_hash == sha256(state.encode()).hexdigest()
                )
            )
            if kind == "expired":
                record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            else:
                await AuthSessionService(session).consume_oauth_state(state)
            await session.commit()
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == 400
    HHOAuthClient.exchange_code.assert_not_awaited()
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("params", [{}, {"code": "code"}, {"state": "state"}])
async def test_callback_requires_code_and_state(
    async_client: AsyncClient, callback_db, params
) -> None:
    response = await async_client.get("/auth/hh/callback", params=params)
    assert response.status_code == 422
    HHOAuthClient.exchange_code.assert_not_awaited()


@pytest.mark.parametrize(
    ("stage", "error_type", "status_code"),
    [
        ("exchange", "temporary", 503),
        ("exchange", "authentication", 400),
        ("profile", "temporary", 503),
        ("profile", "malformed", 502),
    ],
)
async def test_external_failure_consumes_state_without_login(
    async_client: AsyncClient,
    callback_db,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    error_type: str,
    status_code: int,
) -> None:
    from job_aggregator.integrations.hh.errors import (
        HHAuthenticationError,
        HHPermanentRequestError,
        HHTemporaryError,
    )

    errors = {
        "temporary": HHTemporaryError,
        "authentication": HHAuthenticationError,
        "malformed": HHPermanentRequestError,
    }
    state = await create_state(callback_db)
    if stage == "exchange":
        HHOAuthClient.exchange_code.side_effect = errors[error_type](
            "private-upstream-body"
        )
    elif error_type == "malformed":
        HHAPIClient.request.return_value = {"id": {"private-upstream-body": True}}
    else:
        HHAPIClient.request.side_effect = errors[error_type]("private-upstream-body")
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == status_code
    assert "set-cookie" not in response.headers
    assert "private-upstream-body" not in response.text
    async with callback_db() as session:
        assert await AuthSessionService(session).consume_oauth_state(state) is False
        for model in (User, HHAccount, UserSession):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
    again = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert again.status_code == 400
    HHOAuthClient.exchange_code.assert_awaited_once()


async def test_failed_commit_rolls_back_all_login_records(
    async_client: AsyncClient, callback_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    state = await create_state(callback_db)
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
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == 500
    assert "set-cookie" not in response.headers
    assert "private-database-details" not in response.text
    async with callback_db() as session:
        assert await AuthSessionService(session).consume_oauth_state(state) is False
        for model in (User, HHAccount, UserSettings, UserSession):
            assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_production_cookie_is_secure(
    app: FastAPI, async_client: AsyncClient, callback_db
) -> None:
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"app_env": "production"}
    )
    state = await create_state(callback_db)
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == 303
    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize(
    "missing", ["hh_client_id", "hh_client_secret", "hh_redirect_uri"]
)
async def test_missing_configuration_uses_sdk_defaults(
    app: FastAPI, async_client: AsyncClient, callback_db, missing: str
) -> None:
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={missing: None}
    )
    state = await create_state(callback_db)
    response = await async_client.get(
        "/auth/hh/callback", params={"code": "private-code", "state": state}
    )
    assert response.status_code == 303
    HHOAuthClient.exchange_code.assert_awaited_once_with(
        "private-code", settings.hh_redirect_uri if missing != "hh_redirect_uri" else ""
    )
    async with callback_db() as session:
        record = await session.scalar(select(OAuthState))
        assert record.consumed_at is not None
