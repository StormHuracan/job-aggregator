from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings
from job_aggregator.db.base import Base
from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.vacancy import VacancyRepository, VacancySaveError
from job_aggregator.db.session import create_engine_and_factory
from job_aggregator.integrations.hh.dto import HHVacancyPage, HHVacancySearchParams
from job_aggregator.schemas.vacancy import VacancyData
from job_aggregator.services.collection import VacancyCollectionService
from job_aggregator.services.saved_searches import (
    SavedSearchCollectionService,
    _SearchCriteria,
)
from tests.factories import make_vacancy_data


class SearchAwareFakeHHClient:
    def __init__(self, responses: dict[str, dict[int, HHVacancyPage | BaseException]]):
        self.responses = responses
        self.calls: list[HHVacancySearchParams] = []

    async def search_vacancies(self, params: HHVacancySearchParams) -> HHVacancyPage:
        self.calls.append(params)
        response = self.responses[params.text][params.page]
        if isinstance(response, BaseException):
            raise response
        return response


@pytest.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # Importing these models registers their tables with Base.metadata.
    from job_aggregator.db.models import (  # noqa: F401
        auth_session,
        collection_progress,
        hh_account,
        hh_account_token,
        saved_search_match,
        user,
        vacancy,
    )

    engine, factory = create_engine_and_factory(
        f"sqlite+aiosqlite:///{tmp_path / 'saved-search-collection.db'}"
    )

    # SQLite's legacy transaction mode may release a SAVEPOINT as the actual
    # transaction when the outer transaction has not emitted BEGIN yet. Force
    # an explicit BEGIN so outer rollback also rolls back nested SAVEPOINTs.
    @event.listens_for(engine.sync_engine, "connect")
    def _disable_driver_transaction_control(dbapi_connection, _record) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _begin_transaction(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _create_user_and_searches(
    factory: async_sessionmaker[AsyncSession],
    *,
    searches: list[dict[str, Any]],
    pages_limit: int = 2,
) -> int:
    async with factory.begin() as session:
        user = User(hh_user_id="hh-user", display_name="Test user")
        session.add(user)
        await session.flush()
        session.add(UserSettings(user_id=user.id, default_pages_limit=pages_limit))
        for data in searches:
            values = dict(data)
            if values.get("user_id") is not None:
                values["user_id"] = user.id
            session.add(SavedSearch(**values))
        await session.flush()
        return user.id


def _page(*items: VacancyData, page: int = 0, pages: int = 1) -> HHVacancyPage:
    return HHVacancyPage(
        items=list(items),
        page=page,
        found=len(items),
        pages=pages,
    )


def _install_fake_builder(monkeypatch, responses):
    import job_aggregator.services.saved_searches as module

    clients: list[SearchAwareFakeHHClient] = []

    def build_collection_service(
        user_id,
        session,
        session_factory,
        settings,
        on_saved=None,
    ):
        client = SearchAwareFakeHHClient(responses)
        clients.append(client)
        return VacancyCollectionService(
            client=client,
            repository=VacancyRepository(session),
            on_saved=on_saved,
        )

    monkeypatch.setattr(module, "build_collection_service", build_collection_service)
    return clients


async def test_empty_active_search_list_does_not_build_collector(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    user_id = await _create_user_and_searches(session_factory, searches=[])
    clients = _install_fake_builder(monkeypatch, {})

    result = await SavedSearchCollectionService(
        session_factory, Settings()
    ).collect_for_user(user_id)

    assert result.user_id == user_id
    assert result.searches == []
    assert (result.created, result.updated, result.skipped, result.failed) == (
        0,
        0,
        0,
        0,
    )
    assert result.new_matches == 0
    assert clients == []


async def test_active_searches_share_vacancy_but_record_separate_matches(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    user_id = await _create_user_and_searches(
        session_factory,
        searches=[
            {
                "user_id": 1,
                "name": "Python",
                "text": "python",
                "min_salary": 100_000,
                "max_salary": None,
                "is_enabled": True,
            },
            {
                "user_id": 1,
                "name": "Backend",
                "text": "backend",
                "min_salary": None,
                "max_salary": 200_000,
                "is_enabled": True,
            },
            {
                "user_id": None,
                "name": "Legacy",
                "text": "legacy",
                "is_enabled": True,
            },
            {
                "user_id": 1,
                "name": "Disabled",
                "text": "disabled",
                "is_enabled": False,
            },
        ],
    )

    async with session_factory.begin() as session:
        other_user = User(hh_user_id="other-hh-user", display_name="Other user")
        session.add(other_user)
        await session.flush()
        session.add(
            SavedSearch(
                user_id=other_user.id,
                name="Foreign",
                text="foreign",
                is_enabled=True,
            )
        )

    vacancy = make_vacancy_data(
        external_id="shared",
        salary_from=120_000,
        salary_to=180_000,
    )
    _install_fake_builder(
        monkeypatch,
        {
            "python": {0: _page(vacancy)},
            "backend": {0: _page(vacancy)},
        },
    )

    result = await SavedSearchCollectionService(
        session_factory, Settings()
    ).collect_for_user(user_id)

    assert [item.search_id for item in result.searches] == sorted(
        item.search_id for item in result.searches
    )
    assert len(result.searches) == 2
    assert all(item.succeeded for item in result.searches)
    assert result.created == 1
    assert result.skipped == 1
    assert result.new_matches == 2

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Vacancy)) == 1
        assert (
            await session.scalar(select(func.count()).select_from(SavedSearchMatch))
            == 2
        )

    repeated = await SavedSearchCollectionService(
        session_factory, Settings()
    ).collect_for_user(user_id)
    assert repeated.created == 0
    assert repeated.new_matches == 0


@pytest.mark.parametrize(
    ("minimum", "maximum", "salary_from", "salary_to", "expected"),
    [
        (100, None, 100, 150, True),
        (100, None, 99, 150, False),
        (100, None, None, 150, False),
        (None, 200, 100, 200, True),
        (None, 200, 100, 201, False),
        (None, 200, 100, None, False),
        (100, 200, 100, 200, True),
        (100, 200, 99, 200, False),
        (100, 200, 100, 201, False),
        (None, None, None, None, True),
    ],
)
def test_salary_matching_boundaries(
    minimum: int | None,
    maximum: int | None,
    salary_from: int | None,
    salary_to: int | None,
    expected: bool,
) -> None:
    criteria = _SearchCriteria(
        search_id=1,
        text="python",
        area=None,
        min_salary=minimum,
        max_salary=maximum,
    )
    vacancy = make_vacancy_data(salary_from=salary_from, salary_to=salary_to)

    assert SavedSearchCollectionService._salary_matches(vacancy, criteria) is expected


async def test_failure_rolls_back_one_search_without_affecting_another(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    user_id = await _create_user_and_searches(
        session_factory,
        searches=[
            {
                "user_id": 1,
                "name": "Broken",
                "text": "broken",
                "is_enabled": True,
            },
            {
                "user_id": 1,
                "name": "Working",
                "text": "working",
                "is_enabled": True,
            },
        ],
    )
    async with session_factory() as session:
        searches = list(
            await session.scalars(
                select(SavedSearch)
                .where(SavedSearch.user_id == user_id)
                .order_by(SavedSearch.id)
            )
        )

    first = make_vacancy_data(external_id="rolled-back")
    second = make_vacancy_data(external_id="committed")
    _install_fake_builder(
        monkeypatch,
        {
            "broken": {
                0: _page(first, page=0, pages=2),
                1: RuntimeError("external error"),
            },
            "working": {0: _page(second)},
        },
    )

    result = await SavedSearchCollectionService(
        session_factory, Settings()
    ).collect_for_user(user_id)

    assert len(result.searches) == 2
    broken = next(item for item in result.searches if item.search_id == searches[0].id)
    working = next(item for item in result.searches if item.search_id == searches[1].id)
    assert broken.succeeded is False
    assert (broken.created, broken.updated, broken.skipped, broken.failed) == (
        0,
        0,
        0,
        0,
    )
    assert working.succeeded is True
    assert working.created == 1

    async with session_factory() as session:
        external_ids = set(await session.scalars(select(Vacancy.external_id)))
        assert external_ids == {"committed"}


async def test_cancellation_propagates_and_rolls_back_current_search(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    user_id = await _create_user_and_searches(
        session_factory,
        searches=[
            {
                "user_id": 1,
                "name": "Python",
                "text": "python",
                "is_enabled": True,
            }
        ],
    )
    first_page_vacancy = make_vacancy_data(external_id="cancelled-run")
    _install_fake_builder(
        monkeypatch,
        {
            "python": {
                0: _page(first_page_vacancy, page=0, pages=2),
                1: asyncio.CancelledError(),
            }
        },
    )

    with pytest.raises(asyncio.CancelledError):
        await SavedSearchCollectionService(
            session_factory, Settings()
        ).collect_for_user(user_id)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Vacancy)) == 0
        assert (
            await session.scalar(select(func.count()).select_from(SavedSearchMatch))
            == 0
        )


async def test_failed_vacancy_is_counted_but_does_not_create_match(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    user_id = await _create_user_and_searches(
        session_factory,
        searches=[
            {
                "user_id": 1,
                "name": "Python",
                "text": "python",
                "is_enabled": True,
            }
        ],
    )
    bad = make_vacancy_data(external_id="bad")
    good = make_vacancy_data(external_id="good")
    _install_fake_builder(monkeypatch, {"python": {0: _page(bad, good)}})

    original_upsert = VacancyRepository.upsert

    async def upsert_with_bad_item(self, vacancy):
        if vacancy.external_id == "bad":
            raise VacancySaveError("invalid vacancy data")
        return await original_upsert(self, vacancy)

    monkeypatch.setattr(VacancyRepository, "upsert", upsert_with_bad_item)

    result = await SavedSearchCollectionService(
        session_factory, Settings()
    ).collect_for_user(user_id)

    assert result.created == 1
    assert result.failed == 1
    assert result.new_matches == 1

    async with session_factory() as session:
        assert list(await session.scalars(select(Vacancy.external_id))) == ["good"]
        matches = list(await session.scalars(select(SavedSearchMatch)))
        assert len(matches) == 1
