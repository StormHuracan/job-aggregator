from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.hh_account_token import HHAccountToken
from job_aggregator.services import TokenService
from tests.factories import make_token_data


async def test_get_current_returns_none_when_empty(
    sqlite_session: AsyncSession,
) -> None:
    service = TokenService(sqlite_session)
    assert await service.get_current() is None


async def test_save_creates_first_record(sqlite_session: AsyncSession) -> None:
    service = TokenService(sqlite_session)
    assert await service.save(make_token_data()) is True
    await sqlite_session.commit()

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "access-1"


async def test_save_updates_existing_record_without_duplicate(
    sqlite_session: AsyncSession,
) -> None:
    service = TokenService(sqlite_session)
    await service.save(make_token_data(access_token="access-1"))
    await sqlite_session.commit()

    assert await service.save(make_token_data(access_token="access-2")) is True
    await sqlite_session.commit()

    count = await sqlite_session.scalar(
        select(func.count()).select_from(HHAccountToken)
    )
    assert count == 1

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "access-2"


async def test_save_returns_false_when_unchanged(sqlite_session: AsyncSession) -> None:
    service = TokenService(sqlite_session)
    tokens = make_token_data()
    assert await service.save(tokens) is True
    await sqlite_session.commit()

    assert await service.save(tokens) is False


async def test_only_one_token_record_can_exist(sqlite_session: AsyncSession) -> None:
    """UNIQUE(singleton) запрещает вторую запись с singleton=True."""
    sqlite_session.add(
        HHAccountToken(
            access_token="a",
            refresh_token="r",
            access_expires_at=datetime(2026, 10, 11, tzinfo=UTC),
        )
    )
    await sqlite_session.commit()

    sqlite_session.add(
        HHAccountToken(
            access_token="b",
            refresh_token="r2",
            access_expires_at=datetime(2026, 10, 11, tzinfo=UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await sqlite_session.commit()


async def test_save_after_rollback_still_single_record(
    sqlite_session: AsyncSession,
) -> None:
    service = TokenService(sqlite_session)
    await service.save(make_token_data(access_token="first"))
    await sqlite_session.rollback()

    assert await service.save(make_token_data(access_token="second")) is True
    await sqlite_session.commit()

    count = await sqlite_session.scalar(
        select(func.count()).select_from(HHAccountToken)
    )
    assert count == 1

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "second"


async def test_save_after_commit_then_rollback(sqlite_session: AsyncSession) -> None:
    service = TokenService(sqlite_session)
    await service.save(make_token_data(access_token="v1"))
    await sqlite_session.commit()

    await service.save(make_token_data(access_token="v2"))
    await sqlite_session.rollback()

    assert await service.save(make_token_data(access_token="v3")) is True
    await sqlite_session.commit()

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "v3"
