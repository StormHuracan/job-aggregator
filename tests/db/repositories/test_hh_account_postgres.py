import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from tests.factories import make_token_data


@pytest.mark.parametrize("existing", [False, True])
async def test_concurrent_saves_keep_one_complete_account(
    pg_session_factory: async_sessionmaker[AsyncSession], existing: bool
) -> None:
    """Первая вставка и обновления сериализуются в транзакциях caller-а."""
    async with pg_session_factory.begin() as session:
        user = User(hh_user_id="42", display_name="Пользователь")
        session.add(user)
        await session.flush()
        user_id = user.id
        if existing:
            await HHAccountRepository(session).save(user_id, make_token_data())

    barrier = asyncio.Barrier(2)

    async def save(suffix: str) -> bool:
        async with pg_session_factory() as session:
            repo = HHAccountRepository(session)
            # Проверяем также обновление уже загруженного ORM-объекта.
            loaded = await repo.get_by_user_id(user_id)
            await barrier.wait()
            changed = await repo.save(
                user_id,
                make_token_data(
                    access_token=f"access-{suffix}", refresh_token=f"refresh-{suffix}"
                ),
            )
            assert session.in_transaction()
            assert session.is_active
            if loaded is not None:
                assert loaded.access_token == f"access-{suffix}"
            await session.commit()
            return changed

    results = await asyncio.wait_for(asyncio.gather(save("a"), save("b")), 10)
    assert results == [True, True]
    async with pg_session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(HHAccount))
        account = await HHAccountRepository(session).get_by_user_id(user_id)
        assert count == 1
        assert account is not None
        assert (account.access_token, account.refresh_token) in {
            ("access-a", "refresh-a"),
            ("access-b", "refresh-b"),
        }


async def test_caller_controls_atomic_rollback(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory.begin() as session:
        user = User(hh_user_id="42", display_name="Пользователь")
        session.add(user)
        await session.flush()
        user_id = user.id

    async with pg_session_factory() as session:
        session.add(UserSettings(user_id=user_id, default_pages_limit=2))
        await HHAccountRepository(session).save(user_id, make_token_data())
        async with pg_session_factory() as observer:
            assert await HHAccountRepository(observer).get_by_user_id(user_id) is None
            assert await observer.get(UserSettings, user_id) is None
        await session.rollback()
        assert session.is_active

    async with pg_session_factory() as session:
        repo = HHAccountRepository(session)
        assert await repo.get_by_user_id(user_id) is None
        assert await session.get(UserSettings, user_id) is None
        assert await repo.save(user_id, make_token_data()) is True
        await session.commit()


async def test_equal_instants_do_not_update_account(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory.begin() as session:
        user = User(hh_user_id="42", display_name="Пользователь")
        session.add(user)
        await session.flush()
        repo = HHAccountRepository(session)
        await repo.save(user.id, make_token_data())
        equivalent = datetime(2030, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
        assert equivalent == datetime(2030, 1, 1, tzinfo=UTC)
        assert (
            await repo.save(user.id, make_token_data(access_expires_at=equivalent))
            is False
        )
