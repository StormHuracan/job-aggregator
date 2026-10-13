from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.repositories import SavedSearchRepository


async def test_list_enabled_returns_only_enabled(sqlite_session: AsyncSession) -> None:
    sqlite_session.add_all(
        [
            SavedSearch(name="A", text="python", is_enabled=True),
            SavedSearch(name="B", text="java", is_enabled=False),
            SavedSearch(name="C", text="go", is_enabled=True),
        ]
    )
    await sqlite_session.commit()

    repo = SavedSearchRepository(sqlite_session)
    result = await repo.list_enabled()

    names = [item.name for item in result]
    assert names == ["A", "C"]
    assert all(item.is_enabled for item in result)


async def test_list_enabled_sorts_by_id(sqlite_session: AsyncSession) -> None:
    sqlite_session.add_all(
        [
            SavedSearch(name="First", text="python", is_enabled=True),
            SavedSearch(name="Second", text="rust", is_enabled=True),
            SavedSearch(name="Third", text="go", is_enabled=True),
        ]
    )
    await sqlite_session.commit()

    repo = SavedSearchRepository(sqlite_session)
    result = await repo.list_enabled()

    ids = [item.id for item in result]
    assert ids == sorted(ids)


async def test_list_enabled_returns_empty_list_when_none_active(
    sqlite_session: AsyncSession,
) -> None:
    sqlite_session.add(
        SavedSearch(name="Disabled", text="python", is_enabled=False),
    )
    await sqlite_session.commit()

    repo = SavedSearchRepository(sqlite_session)
    result = await repo.list_enabled()

    assert result == []


async def test_list_enabled_returns_empty_list_when_no_rows(
    sqlite_session: AsyncSession,
) -> None:
    repo = SavedSearchRepository(sqlite_session)
    result = await repo.list_enabled()

    assert result == []
