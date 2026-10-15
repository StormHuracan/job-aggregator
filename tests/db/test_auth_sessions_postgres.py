import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.user import User
from job_aggregator.services.auth_sessions import AuthSessionService


async def test_concurrent_rolling_renewal_creates_one_replacement_session(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    async with pg_session_factory() as setup_session:
        user = User(hh_user_id="hh-42", display_name="Daniil")
        setup_session.add(user)
        await setup_session.flush()
        token = await AuthSessionService(
            setup_session,
            clock=lambda: now,
        ).create_session(user.id)
        await setup_session.commit()

    async def authenticate() -> str | None:
        async with pg_session_factory() as session:
            authentication = await AuthSessionService(
                session,
                clock=lambda: now + timedelta(days=6),
            ).authenticate_session(token)
            await session.commit()
            if authentication is None:
                return None
            return authentication.replacement_token

    replacement_tokens = await asyncio.gather(authenticate(), authenticate())

    assert sum(token is not None for token in replacement_tokens) == 1
