import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.telegram_link_token import TelegramLinkToken
from job_aggregator.db.models.user import User
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService

SESSION_COOKIE_NAME = "job_aggregator_session"


async def _create_user_and_token(session: AsyncSession, label: str) -> tuple[User, str]:
    user = User(hh_user_id=f"hh-{label}", display_name=label)
    session.add(user)
    await session.flush()

    token = await AuthSessionService(session).create_session(user.id)
    await session.commit()

    return user, token


@pytest.fixture
async def api_session_override(app, sqlite_session: AsyncSession):
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_telegram_link_requires_valid_session(
    async_client: AsyncClient,
    api_session_override,
) -> None:
    response = await async_client.post("/me/telegram/link")
    assert response.status_code == 401

    async_client.cookies.set(SESSION_COOKIE_NAME, "invalid-token")
    response = await async_client.post("/me/telegram/link")
    assert response.status_code == 401


async def test_telegram_disconnect_is_idempotent(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
) -> None:
    _, token = await _create_user_and_token(sqlite_session, "telegram-disconnect")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)

    first = await async_client.delete("/me/telegram")
    second = await async_client.delete("/me/telegram")

    assert first.status_code == 204
    assert second.status_code == 204


async def test_telegram_link_returns_url_and_expiration(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setattr(
        "job_aggregator.api.user.get_settings",
        lambda: SimpleNamespace(
            telegram_enabled=True,
            telegram_bot_token="test-token",
            telegram_bot_username="@test_bot",
        ),
    )

    _, token = await _create_user_and_token(sqlite_session, "telegram-link")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)

    response = await async_client.post("/me/telegram/link")

    assert response.status_code == 200

    data = response.json()
    assert data["url"].startswith("https://t.me/test_bot?start=")
    assert "expires_at" in data

    link_token = parse_qs(urlparse(data["url"]).query)["start"][0]
    stored_token = await sqlite_session.scalar(
        select(TelegramLinkToken).where(
            TelegramLinkToken.token_hash
            == hashlib.sha256(link_token.encode()).hexdigest()
        )
    )

    assert stored_token is not None
    assert stored_token.consumed_at is None


async def test_telegram_link_returns_503_when_disabled(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setattr(
        "job_aggregator.api.user.get_settings",
        lambda: SimpleNamespace(
            telegram_enabled=False,
            telegram_bot_token=None,
            telegram_bot_username=None,
        ),
    )

    _, token = await _create_user_and_token(sqlite_session, "telegram-disabled")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)

    response = await async_client.post("/me/telegram/link")

    assert response.status_code == 503


async def test_telegram_link_expires_in_ten_minutes(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setattr(
        "job_aggregator.api.user.get_settings",
        lambda: SimpleNamespace(
            telegram_enabled=True,
            telegram_bot_token="test-token",
            telegram_bot_username="test_bot",
        ),
    )

    _, token = await _create_user_and_token(sqlite_session, "telegram-expiration")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)

    before = datetime.now(UTC)
    response = await async_client.post("/me/telegram/link")
    after = datetime.now(UTC)

    assert response.status_code == 200

    expires_at = datetime.fromisoformat(response.json()["expires_at"])
    assert before + timedelta(minutes=10) <= expires_at
    assert expires_at <= after + timedelta(minutes=10)


async def test_new_telegram_link_invalidates_previous_token(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setattr(
        "job_aggregator.api.user.get_settings",
        lambda: SimpleNamespace(
            telegram_enabled=True,
            telegram_bot_token="test-token",
            telegram_bot_username="test_bot",
        ),
    )

    user, token = await _create_user_and_token(sqlite_session, "telegram-relink")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)

    first = await async_client.post("/me/telegram/link")
    second = await async_client.post("/me/telegram/link")

    assert first.status_code == 200
    assert second.status_code == 200

    first_token = parse_qs(urlparse(first.json()["url"]).query)["start"][0]
    second_token = parse_qs(urlparse(second.json()["url"]).query)["start"][0]

    assert first_token != second_token

    stored_tokens = list(
        (
            await sqlite_session.scalars(
                select(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id)
            )
        ).all()
    )

    assert len(stored_tokens) == 1
    assert (
        stored_tokens[0].token_hash == hashlib.sha256(second_token.encode()).hexdigest()
    )
