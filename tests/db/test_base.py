import asyncio

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base, TimestampMixin, _utc_now
from job_aggregator.db.session import create_engine_and_factory


class DummyModel(TimestampMixin, Base):
    __tablename__ = "test_dummy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(default="foo")


@pytest.fixture
async def session():
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with factory() as s:
            yield s
    finally:
        await engine.dispose()


def test_utc_now_is_timezone_aware() -> None:
    now = _utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


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
