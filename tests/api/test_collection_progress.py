from unittest.mock import Mock

import pytest

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.user import User
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
async def progress_api(app, sqlite_session, monkeypatch):
    """Настоящие API, сборщик и persistence; только HH заменён fake-клиентом."""
    users = [User(id=i, hh_user_id=f"hh-{i}", display_name="Тест") for i in (1, 2)]
    sqlite_session.add_all(users)
    await sqlite_session.commit()
    sqlite_session.expunge_all()
    current_user = users[0]
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: sqlite_session
    app.state.session_factory = object()
    hh = FakeHHClient(
        pages={
            i: HHVacancyPage(
                items=[make_vacancy_data(external_id=str(i))], page=i, found=3, pages=3
            )
            for i in range(3)
        }
    )
    builder = Mock(
        side_effect=lambda **kwargs: VacancyCollectionService(
            hh, VacancyRepository(sqlite_session)
        )
    )
    monkeypatch.setattr(
        "job_aggregator.api.collection.build_collection_service", builder
    )
    return hh, current_user, users[1], builder


async def test_repeated_runs_continue_after_reload_and_restart_explicitly(
    async_client, progress_api, sqlite_session
):
    hh, *_ = progress_api
    first = await async_client.post(ENDPOINT, json=BODY)
    sqlite_session.expunge_all()
    second = await async_client.post(ENDPOINT, json=BODY)
    assert [call.page for call in hh.calls] == [0, 1]
    assert first.json() == {
        "created": 1,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "next_page": 1,
        "exhausted": False,
    }
    assert second.json()["created"] == 1
    restarted = await async_client.post(ENDPOINT, json={**BODY, "restart": True})
    assert hh.calls[-1].page == 0
    assert restarted.json()["skipped"] == 1
    assert restarted.json()["next_page"] == 1


async def test_limit_change_and_known_vacancies_do_not_reset_or_stop_search(
    async_client, progress_api
):
    hh, *_ = progress_api
    await async_client.post(ENDPOINT, json=BODY)
    await async_client.post(ENDPOINT, json={**BODY, "text": "other", "pages_limit": 3})
    response = await async_client.post(ENDPOINT, json={**BODY, "pages_limit": 3})
    assert [call.page for call in hh.calls] == [0, 0, 1, 2, 1, 2]
    assert (
        response.json()["skipped"],
        response.json()["next_page"],
        response.json()["exhausted"],
    ) == (2, 3, True)
    exhausted = await async_client.post(ENDPOINT, json=BODY)
    assert exhausted.json() == {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "next_page": 3,
        "exhausted": True,
    }
    assert len(hh.calls) == 6


async def test_search_positions_are_isolated_by_owner_and_region(
    async_client, progress_api, app
):
    hh, _, other, _ = progress_api
    for body in (
        BODY,
        {**BODY, "area": "1"},
        {**BODY, "text": "other"},
        {**BODY, "text": " python "},
    ):
        assert (await async_client.post(ENDPOINT, json=body)).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: other
    await async_client.post(ENDPOINT, json=BODY)
    assert [call.page for call in hh.calls] == [0, 0, 0, 1, 0]


async def test_failed_request_keeps_previous_position(async_client, progress_api):
    hh, *_ = progress_api
    await async_client.post(ENDPOINT, json=BODY)
    hh.error = HHTemporaryError("private")
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.status_code == 503
    assert "private" not in response.text
    hh.error = None
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.status_code == 200
    assert [call.page for call in hh.calls] == [0, 1, 1]
