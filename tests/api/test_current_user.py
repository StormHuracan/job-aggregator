from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import SESSION_COOKIE_NAME, get_current_user
from job_aggregator.db.models.auth_session import UserSession
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService


def _cookie_attrs(set_cookie: str) -> set[str]:
    return {part.strip().lower() for part in set_cookie.split(";")[1:]}


async def _create_user(session: AsyncSession, hh_user_id: str = "hh-1") -> User:
    user = User(hh_user_id=hh_user_id, display_name="Test User")
    session.add(user)
    await session.commit()
    return user


async def _create_session(session: AsyncSession, user: User) -> str:
    token = await AuthSessionService(session).create_session(user.id)
    await session.commit()
    return token


async def _force_near_expiry(session: AsyncSession) -> None:
    """Перевести все сессии в окно rolling (expires_at - now <= 1 день)."""
    await session.execute(
        UserSession.__table__.update().values(
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
    )
    await session.commit()


@pytest.fixture
def protected_app(app, sqlite_session):
    """Подменяет БД и добавляет защищённый маршрут в общее приложение."""

    async def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_get_db

    @app.get("/dependency-test/me")
    async def me(user: User = Depends(get_current_user)):
        return {"id": user.id, "display_name": user.display_name}

    yield app

    app.dependency_overrides.clear()
    app.router.routes = [
        r for r in app.router.routes if getattr(r, "path", "") != "/dependency-test/me"
    ]


async def test_valid_session_returns_user(
    protected_app, async_client, sqlite_session
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "display_name": "Test User"}


async def test_missing_cookie_returns_401(protected_app, async_client) -> None:
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}


async def test_unknown_cookie_returns_401(protected_app, async_client) -> None:
    async_client.cookies.set(SESSION_COOKIE_NAME, "unknown")
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 401
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}


async def test_expired_session_returns_401(
    protected_app, async_client, sqlite_session
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await sqlite_session.execute(
        UserSession.__table__.update().values(
            expires_at=datetime.now(UTC) - timedelta(minutes=1)
        )
    )
    await sqlite_session.commit()

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 401


async def test_revoked_session_returns_401(
    protected_app, async_client, sqlite_session
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await sqlite_session.execute(
        UserSession.__table__.update().values(revoked_at=datetime.now(UTC))
    )
    await sqlite_session.commit()

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 401


async def test_valid_session_but_missing_user_returns_401(
    protected_app, async_client, sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)

    async def fake_get_by_id(self, user_id: int):
        return None

    monkeypatch.setattr(UserRepository, "get_by_id", fake_get_by_id)

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 401


async def test_rolling_rotates_session_and_cookie(
    protected_app, async_client, sqlite_session
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await _force_near_expiry(sqlite_session)

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert set_cookie.startswith(f"{SESSION_COOKIE_NAME}=")

    attrs = _cookie_attrs(set_cookie)
    assert "httponly" in attrs
    assert "path=/" in attrs
    assert "samesite=lax" in attrs
    assert "max-age=604800" in attrs
    assert "secure" not in attrs

    sessions = (await sqlite_session.execute(select(UserSession))).scalars().all()
    assert len(sessions) == 2
    assert sum(1 for s in sessions if s.revoked_at is not None) == 1
    assert sum(1 for s in sessions if s.revoked_at is None) == 1


async def test_no_rolling_when_not_near_expiry(
    protected_app, async_client, sqlite_session
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 200
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}

    sessions = (await sqlite_session.execute(select(UserSession))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


async def test_rolling_commit_failure_keeps_old_session_no_cookie(
    protected_app, async_client, sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await _force_near_expiry(sqlite_session)

    async def failing_commit() -> None:
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(sqlite_session, "commit", failing_commit)

    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/dependency-test/me")

    assert response.status_code == 200
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}

    monkeypatch.undo()
    sessions = (await sqlite_session.execute(select(UserSession))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


async def test_https_rolls_with_secure_flag(protected_app, app, sqlite_session) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await _force_near_expiry(sqlite_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test"
    ) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        response = await client.get("/dependency-test/me")

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "secure" in _cookie_attrs(set_cookie)


async def test_health_route_is_public(async_client) -> None:
    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
