import pytest

from job_aggregator.db.base import Base
from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.repositories import SavedSearchRepository
from job_aggregator.db.session import create_engine_and_factory


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


async def test_list_enabled_returns_only_enabled(session) -> None:
    session.add_all(
        [
            SavedSearch(name="A", text="python", is_enabled=True),
            SavedSearch(name="B", text="java", is_enabled=False),
            SavedSearch(name="C", text="go", is_enabled=True),
        ]
    )
    await session.commit()

    repo = SavedSearchRepository(session)
    result = await repo.list_enabled()

    names = [item.name for item in result]
    assert names == ["A", "C"]
    assert all(item.is_enabled for item in result)


async def test_list_enabled_sorts_by_id(session) -> None:
    session.add_all(
        [
            SavedSearch(name="First", text="python", is_enabled=True),
            SavedSearch(name="Second", text="rust", is_enabled=True),
            SavedSearch(name="Third", text="go", is_enabled=True),
        ]
    )
    await session.commit()

    repo = SavedSearchRepository(session)
    result = await repo.list_enabled()

    ids = [item.id for item in result]
    assert ids == sorted(ids)


async def test_list_enabled_returns_empty_list_when_none_active(session) -> None:
    session.add(
        SavedSearch(name="Disabled", text="python", is_enabled=False),
    )
    await session.commit()

    repo = SavedSearchRepository(session)
    result = await repo.list_enabled()

    assert result == []


async def test_list_enabled_returns_empty_list_when_no_rows(session) -> None:
    repo = SavedSearchRepository(session)
    result = await repo.list_enabled()

    assert result == []
