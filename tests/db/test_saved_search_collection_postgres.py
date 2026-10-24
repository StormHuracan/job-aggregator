from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings
from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.dto import HHVacancyPage
from job_aggregator.services.collection import VacancyCollectionService
from job_aggregator.services.saved_searches import SavedSearchCollectionService
from tests.factories import make_vacancy_data
from tests.fakes.hh import FakeHHClient


@pytest.mark.parametrize(
    ("fail_after_first_page", "expected_succeeded", "expected_created"),
    [(False, True, 1), (True, False, 0)],
    ids=["commit-search", "rollback-search"],
)
async def test_saved_search_vacancies_and_matches_share_transaction(
    pg_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch,
    fail_after_first_page: bool,
    expected_succeeded: bool,
    expected_created: int,
) -> None:
    async with pg_session_factory.begin() as session:
        user = User(hh_user_id="pg-user", display_name="Postgres test")
        session.add(user)
        await session.flush()
        session.add(UserSettings(user_id=user.id, default_pages_limit=2))
        search = SavedSearch(
            user_id=user.id,
            name="Python",
            text="python",
            is_enabled=True,
        )
        session.add(search)
        await session.flush()
        user_id = user.id
        search_id = search.id

    vacancy_data = make_vacancy_data(external_id="transaction-test")
    pages = {
        0: HHVacancyPage(
            items=[vacancy_data],
            page=0,
            found=1,
            pages=2 if fail_after_first_page else 1,
        )
    }

    def build_collection_service(
        user_id,
        session,
        session_factory,
        settings,
        on_saved=None,
    ):
        return VacancyCollectionService(
            client=cast(HHClient, FakeHHClient(pages=pages)),
            repository=VacancyRepository(session),
            on_saved=on_saved,
        )

    import job_aggregator.services.saved_searches as module

    monkeypatch.setattr(module, "build_collection_service", build_collection_service)

    result = await SavedSearchCollectionService(
        pg_session_factory, Settings()
    ).collect_for_user(user_id)

    assert len(result.searches) == 1
    search_result = result.searches[0]
    assert search_result.search_id == search_id
    assert search_result.succeeded is expected_succeeded
    assert search_result.created == expected_created
    assert search_result.new_matches == expected_created

    async with pg_session_factory() as session:
        vacancies = list(await session.scalars(select(Vacancy)))
        matches = list(await session.scalars(select(SavedSearchMatch)))
        if expected_succeeded:
            assert [vacancy.external_id for vacancy in vacancies] == [
                "transaction-test"
            ]
            assert len(matches) == 1
            assert matches[0].saved_search_id == search_id
            assert matches[0].vacancy_id == vacancies[0].id
        else:
            assert vacancies == []
            assert matches == []
