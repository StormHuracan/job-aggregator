import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from job_aggregator.db.base import Base, TimestampMixin, _utc_now
from job_aggregator.db.session import create_engine_and_factory


class DummyBase(DeclarativeBase):
    pass


class DummyModel(TimestampMixin, DummyBase):
    __tablename__ = "test_dummy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(default="foo")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(DummyBase.metadata.create_all)
        async with factory() as s:
            yield s
    finally:
        await engine.dispose()


def test_utc_now_is_timezone_aware() -> None:
    now = _utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_dummy_model_does_not_pollute_application_metadata() -> None:
    assert "test_dummy" not in Base.metadata.tables


async def test_timestamps_filled_on_insert(session) -> None:
    obj = DummyModel(name="a")
    session.add(obj)
    await session.commit()
    await session.refresh(obj)

    assert obj.created_at is not None
    assert obj.updated_at is not None
    delta = abs((obj.updated_at - obj.created_at).total_seconds())
    assert delta < 1


async def test_update_changes_updated_at_only(session) -> None:
    obj = DummyModel(name="a")
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    created_before = obj.created_at
    updated_before = obj.updated_at

    await asyncio.sleep(0.01)
    obj.name = "b"
    await session.commit()
    await session.refresh(obj)

    assert obj.created_at == created_before
    assert obj.updated_at > updated_before
