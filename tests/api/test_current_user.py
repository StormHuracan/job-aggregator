from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import SESSION_COOKIE_NAME, get_current_user
from job_aggregator.db.models.auth_session import UserSession
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService


def _build_app(sqlite_session: AsyncSession) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def me(user: User = Depends(get_current_user)) -> dict[str, object]:
        return {"id": user.id, "display_name": user.display_name}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    async def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_get_db
    return app


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


def _client(app: FastAPI, base_url: str = "http://test") -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base_url)


def _cookie_attrs(set_cookie: str) -> set[str]:
    return {part.strip().lower() for part in set_cookie.split(";")[1:]}


async def test_valid_session_returns_user(sqlite_session: AsyncSession) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "display_name": "Test User"}


async def test_missing_cookie_returns_401(sqlite_session: AsyncSession) -> None:
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}


async def test_unknown_cookie_returns_401(sqlite_session: AsyncSession) -> None:
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: "unknown"})

    assert response.status_code == 401
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}


async def test_expired_session_returns_401(sqlite_session: AsyncSession) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await sqlite_session.execute(
        UserSession.__table__.update().values(
            expires_at=datetime.now(UTC) - timedelta(minutes=1)
        )
    )
    await sqlite_session.commit()
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 401


async def test_revoked_session_returns_401(sqlite_session: AsyncSession) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await sqlite_session.execute(
        UserSession.__table__.update().values(revoked_at=datetime.now(UTC))
    )
    await sqlite_session.commit()
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 401


async def test_valid_session_but_missing_user_returns_401(
    sqlite_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)

    async def fake_get_by_id(self, user_id: int):  # noqa: ANN001
        return None

    monkeypatch.setattr(UserRepository, "get_by_id", fake_get_by_id)
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 401


async def test_rolling_rotates_session_and_cookie(
    sqlite_session: AsyncSession,
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await _force_near_expiry(sqlite_session)
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

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


async def test_no_rolling_when_not_near_expiry(sqlite_session: AsyncSession) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 200
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}

    sessions = (await sqlite_session.execute(select(UserSession))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


async def test_rolling_commit_failure_keeps_old_session_no_cookie(
    sqlite_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await _force_near_expiry(sqlite_session)
    app = _build_app(sqlite_session)

    async def failing_commit() -> None:
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(sqlite_session, "commit", failing_commit)

    async with _client(app) as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 200
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}

    monkeypatch.undo()
    sessions = (await sqlite_session.execute(select(UserSession))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


async def test_https_rolls_with_secure_flag(sqlite_session: AsyncSession) -> None:
    user = await _create_user(sqlite_session)
    token = await _create_session(sqlite_session, user)
    await _force_near_expiry(sqlite_session)
    app = _build_app(sqlite_session)

    async with _client(app, base_url="https://test") as client:
        response = await client.get("/me", cookies={SESSION_COOKIE_NAME: token})

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "secure" in _cookie_attrs(set_cookie)


async def test_health_route_is_public(sqlite_session: AsyncSession) -> None:
    app = _build_app(sqlite_session)

    async with _client(app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
