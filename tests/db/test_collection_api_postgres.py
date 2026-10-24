import asyncio
from unittest.mock import Mock

import pytest
from sqlalchemy import event, func, select

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.collection_progress import CollectionProgress
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.dto import HHVacancyPage
from job_aggregator.integrations.hh.errors import HHTemporaryError
from job_aggregator.services.collection import VacancyCollectionService
from tests.factories import make_vacancy_data
from tests.fakes.hh import FakeHHClient

ENDPOINT = "/collection/hh/run"
BODY = {"text": "python", "area": None, "pages_limit": 1}


@pytest.fixture
async def collection_app(app, pg_session_factory, monkeypatch):
    """Настоящие транзакции API и сборщика, отдельная сессия на запрос."""
    async with pg_session_factory.begin() as session:
        user = User(id=1, hh_user_id="collection", display_name="Тест")
        session.add(user)
    app.dependency_overrides[get_current_user] = lambda: user

    async def session_dependency():
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = session_dependency
    app.state.session_factory = pg_session_factory
    hh = FakeHHClient(
        pages={
            i: HHVacancyPage(
                items=[make_vacancy_data(external_id=str(i))], page=i, found=3, pages=3
            )
            for i in range(3)
        }
    )
    monkeypatch.setattr(
        "job_aggregator.api.collection.build_collection_service",
        Mock(
            side_effect=lambda **kwargs: VacancyCollectionService(
                hh, VacancyRepository(kwargs["session"])
            )
        ),
    )
    return hh


@pytest.mark.parametrize("failure", ["network", "cancel", "commit"])
@pytest.mark.parametrize("restart", [False, True])
async def test_failed_run_rolls_back_vacancies_and_progress(
    async_client,
    collection_app,
    pg_session_factory,
    monkeypatch,
    failure,
    restart,
):
    hh = collection_app
    assert (await async_client.post(ENDPOINT, json=BODY)).status_code == 200
    original = hh.search_vacancies

    async def fail_second_page(params):
        if params.page == (1 if restart else 2):
            if failure == "cancel":
                raise asyncio.CancelledError
            raise HHTemporaryError("private")
        return await original(params)

    def fail_commit(session):
        raise RuntimeError("private")

    if failure == "commit":
        event.listen(
            pg_session_factory.class_.sync_session_class, "before_commit", fail_commit
        )
    else:
        monkeypatch.setattr(hh, "search_vacancies", fail_second_page)
    try:
        if failure == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await async_client.post(
                    ENDPOINT, json={**BODY, "pages_limit": 2, "restart": restart}
                )
        else:
            response = await async_client.post(
                ENDPOINT, json={**BODY, "pages_limit": 2, "restart": restart}
            )
            assert response.status_code == (500 if failure == "commit" else 503)
    finally:
        if failure == "commit":
            event.remove(
                pg_session_factory.class_.sync_session_class,
                "before_commit",
                fail_commit,
            )
        monkeypatch.setattr(hh, "search_vacancies", original)
    async with pg_session_factory() as session:
        progress = await session.scalar(select(CollectionProgress))
        assert progress.next_page == 1
        assert await session.scalar(select(func.count()).select_from(Vacancy)) == 1
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.json()["created"] == 1
    assert response.json()["next_page"] == 2


async def test_concurrent_api_runs_use_distinct_pages(async_client, collection_app):
    responses = await asyncio.wait_for(
        asyncio.gather(
            async_client.post(ENDPOINT, json=BODY),
            async_client.post(ENDPOINT, json=BODY),
        ),
        5,
    )
    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(r.json()["next_page"] for r in responses) == [1, 2]
    assert [call.page for call in collection_app.calls] == [0, 1]
