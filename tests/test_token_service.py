from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from job_aggregator.db.base import Base
from job_aggregator.db.models.hh_account_token import HHAccountToken
from job_aggregator.db.session import create_engine_and_factory
from job_aggregator.schemas.hh_token import HHAccountTokenData
from job_aggregator.services import TokenService


@pytest.fixture
async def session():
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


def _token_data(access: str = "access-1") -> HHAccountTokenData:
    return HHAccountTokenData(
        access_token=access,
        refresh_token="refresh-1",
        access_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def test_hh_account_token_data_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        HHAccountTokenData(
            access_token="a",
            refresh_token="r",
            access_expires_at=datetime(2030, 1, 1, 12, 0, 0),
        )


def test_hh_account_token_data_normalizes_to_utc() -> None:
    tz = timezone(timedelta(hours=3))
    data = HHAccountTokenData(
        access_token="a",
        refresh_token="r",
        access_expires_at=datetime(2030, 1, 1, 12, 0, 0, tzinfo=tz),
    )
    assert data.access_expires_at.utcoffset() == timedelta(0)


async def test_get_current_returns_none_when_empty(session) -> None:
    service = TokenService(session)
    assert await service.get_current() is None


async def test_save_creates_first_record(session) -> None:
    service = TokenService(session)
    assert await service.save(_token_data()) is True
    await session.commit()

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "access-1"


async def test_save_updates_existing_record_without_duplicate(session) -> None:
    service = TokenService(session)
    await service.save(_token_data(access="access-1"))
    await session.commit()

    assert await service.save(_token_data(access="access-2")) is True
    await session.commit()

    count = await session.scalar(select(func.count()).select_from(HHAccountToken))
    assert count == 1

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "access-2"


async def test_save_returns_false_when_unchanged(session) -> None:
    service = TokenService(session)
    tokens = _token_data()
    assert await service.save(tokens) is True
    await session.commit()

    assert await service.save(tokens) is False


async def test_only_one_token_record_can_exist(session) -> None:
    """UNIQUE(singleton) запрещает создать вторую запись с is_enabled=True."""
    session.add(
        HHAccountToken(
            access_token="a",
            refresh_token="r",
            access_expires_at=datetime.now(UTC),
        )
    )
    await session.commit()

    session.add(
        HHAccountToken(
            access_token="b",
            refresh_token="r2",
            access_expires_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_save_after_rollback_still_single_record(session) -> None:
    """После rollback первой попытки повторный save работает, дубликатов нет."""
    service = TokenService(session)
    await service.save(_token_data(access="first"))
    await session.rollback()

    assert await service.save(_token_data(access="second")) is True
    await session.commit()

    count = await session.scalar(select(func.count()).select_from(HHAccountToken))
    assert count == 1

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "second"


async def test_save_after_commit_then_rollback(session) -> None:
    """После успешного save + rollback повторный save не падает."""
    service = TokenService(session)
    await service.save(_token_data(access="v1"))
    await session.commit()

    await service.save(_token_data(access="v2"))
    await session.rollback()

    assert await service.save(_token_data(access="v3")) is True
    await session.commit()

    current = await service.get_current()
    assert current is not None
    assert current.access_token == "v3"
