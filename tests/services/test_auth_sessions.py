from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.auth_session import OAuthState, UserSession
from job_aggregator.db.models.user import User
from job_aggregator.services.auth_sessions import AuthSessionService


async def _user(sqlite_session: AsyncSession) -> User:
    user = User(hh_user_id="hh-42", display_name="Daniil")
    sqlite_session.add(user)
    await sqlite_session.flush()
    return user


async def test_oauth_state_is_consumed_once_and_raw_value_is_not_stored(
    sqlite_session: AsyncSession,
) -> None:
    service = AuthSessionService(sqlite_session)

    state = await service.create_oauth_state()
    state_1 = await service.create_oauth_state()
    stored_state = await sqlite_session.scalar(select(OAuthState))

    assert stored_state is not None
    assert stored_state.state_hash != state
    assert await service.consume_oauth_state(state) is True
    assert await service.consume_oauth_state(state) is False
    assert state != state_1

async def test_expired_oauth_state_cannot_be_consumed(
    sqlite_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    service = AuthSessionService(sqlite_session, clock=lambda: now)

    state = await service.create_oauth_state()
    expired_service = AuthSessionService(
        sqlite_session,
        clock=lambda: now + timedelta(minutes=11),
    )

    assert await expired_service.consume_oauth_state(state) is False


async def test_session_returns_owner_and_raw_token_is_not_stored(
    sqlite_session: AsyncSession,
) -> None:
    user = await _user(sqlite_session)
    service = AuthSessionService(sqlite_session)

    token = await service.create_session(user.id)
    stored_session = await sqlite_session.scalar(select(UserSession))

    assert stored_session is not None
    assert stored_session.token_hash != token
    assert await service.get_user_id(token) == user.id


async def test_expired_or_revoked_session_cannot_return_owner(
    sqlite_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    user = await _user(sqlite_session)
    service = AuthSessionService(sqlite_session, clock=lambda: now)
    token = await service.create_session(user.id)

    expired_service = AuthSessionService(
        sqlite_session,
        clock=lambda: now + timedelta(days=7, seconds=1),
    )
    assert await expired_service.get_user_id(token) is None

    valid_token = await service.create_session(user.id)
    await service.revoke_session(valid_token)
    assert await service.get_user_id(valid_token) is None


async def test_revoke_session_does_not_affect_other_user_session(
    sqlite_session: AsyncSession,
) -> None:
    user = await _user(sqlite_session)
    service = AuthSessionService(sqlite_session)
    first_token = await service.create_session(user.id)
    second_token = await service.create_session(user.id)

    await service.revoke_session(first_token)

    assert await service.get_user_id(first_token) is None
    assert await service.get_user_id(second_token) == user.id


async def test_authenticate_session_rotates_token_near_expiration(
    sqlite_session: AsyncSession,
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    user = await _user(sqlite_session)
    service = AuthSessionService(sqlite_session, clock=lambda: now)
    old_token = await service.create_session(user.id)
    renewal_service = AuthSessionService(
        sqlite_session,
        clock=lambda: now + timedelta(days=6),
    )

    authentication = await renewal_service.authenticate_session(old_token)

    assert authentication is not None
    assert authentication.user_id == user.id
    assert authentication.replacement_token is not None
    assert await renewal_service.get_user_id(old_token) is None
    assert (
        await renewal_service.get_user_id(authentication.replacement_token) == user.id
    )
