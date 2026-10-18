import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.repositories.user import UserRepository


async def test_concurrent_get_or_create_returns_one_user(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Два одновременных OAuth-входа одного HH-профиля создают одного пользователя."""
    barrier = asyncio.Barrier(2)

    async def login() -> int:
        async with pg_session_factory() as session:
            repo = UserRepository(session)
            await barrier.wait()
            user = await repo.get_or_create("42", "Ivan")
            await session.commit()
            return user.id

    first_id, second_id = await asyncio.gather(login(), login())

    assert first_id == second_id

    async with pg_session_factory() as session:
        users = await session.scalar(select(func.count()).select_from(User))
        settings = await session.scalar(select(func.count()).select_from(UserSettings))
    assert users == 1
    assert settings == 1
