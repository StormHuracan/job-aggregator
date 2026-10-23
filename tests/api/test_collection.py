import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHIntegrationError,
    HHPermanentRequestError,
    HHRateLimitError,
    HHTemporaryError,
)
from job_aggregator.schemas.collection import CollectionRunProgressResponse
from job_aggregator.services.hh_requests import HHAccountNotConnectedError
from tests.factories import make_vacancy_data

ENDPOINT = "/collection/hh/run"
BODY = {"text": "python", "area": None, "pages_limit": 2}


async def test_collection_requires_current_session(app, async_client):
    app.dependency_overrides[get_db_session] = lambda: AsyncMock(spec=AsyncSession)
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.status_code == 401


@pytest.fixture
async def collection_api(app, sqlite_session, monkeypatch):
    """Реальные API и транзакции; подменяется только composition-граница HH."""
    user = User(id=42, hh_user_id="hh-42", display_name="Пользователь")
    sqlite_session.add_all(
        [
            User(id=i, hh_user_id=f"hh-{i}", display_name="Пользователь")
            for i in (42, 75)
        ]
    )
    await sqlite_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: sqlite_session
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)
    app.state.session_factory = factory
    service = AsyncMock()
    service.collect_pages_with_progress.return_value = CollectionRunProgressResponse(
        created=0, updated=0, skipped=0, failed=0, next_page=1, exhausted=False
    )
    builder = Mock(return_value=service)
    monkeypatch.setattr(
        "job_aggregator.api.collection.build_collection_service", builder
    )
    return service, builder, user, factory


@pytest.mark.parametrize("user_id", [42, 75])
async def test_collection_passes_current_owner_and_params(
    async_client, collection_api, sqlite_session, user_id
):
    service, builder, user, factory = collection_api
    user.id = user_id
    response = await async_client.post(ENDPOINT, json={**BODY, "user_id": 999})
    assert response.status_code == 200
    assert response.json() == {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "next_page": 1,
        "exhausted": False,
    }
    assert builder.call_args.kwargs["user_id"] == user_id
    assert builder.call_args.kwargs["session"] is sqlite_session
    assert builder.call_args.kwargs["session_factory"] is factory
    params, pages_limit = service.collect_pages_with_progress.call_args.args
    assert (params.text, params.area, params.page, pages_limit) == (
        "python",
        None,
        0,
        2,
    )


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "text": "  "},
        {**BODY, "pages_limit": 0},
        {"text": "python", "pages_limit": 1},
    ],
)
async def test_collection_validates_before_running(async_client, collection_api, body):
    service, *_ = collection_api
    response = await async_client.post(ENDPOINT, json=body)
    assert response.status_code == 422
    service.collect_pages_with_progress.assert_not_awaited()


async def test_collection_commits_success_including_rejected_items(
    async_client, collection_api, sqlite_session
):
    service, _, _, factory = collection_api

    async def collect(*args):
        sqlite_session.add(Vacancy(**asdict(make_vacancy_data())))
        await sqlite_session.flush()
        return CollectionRunProgressResponse(
            created=1, updated=0, skipped=0, failed=1, next_page=1, exhausted=False
        )

    service.collect_pages_with_progress.side_effect = collect
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.status_code == 200
    assert response.json()["failed"] == 1
    async with factory() as check:
        assert await check.scalar(select(func.count()).select_from(Vacancy)) == 1


@pytest.mark.parametrize(
    "error,status",
    [
        (HHAccountNotConnectedError("private-token"), 409),
        (HHAuthenticationError("private-token"), 409),
        (HHTemporaryError("private-response"), 503),
        (HHRateLimitError("private-response"), 503),
        (HHPermanentRequestError("private-response"), 502),
        (HHIntegrationError("private-response"), 502),
        (SQLAlchemyError("private-sql"), 500),
        (RuntimeError("private-internal"), 500),
    ],
)
async def test_collection_rolls_back_and_hides_internal_errors(
    async_client, collection_api, sqlite_session, error, status
):
    service, _, _, factory = collection_api

    async def collect(*args):
        sqlite_session.add(Vacancy(**asdict(make_vacancy_data())))
        await sqlite_session.flush()
        raise error

    service.collect_pages_with_progress.side_effect = collect
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)
    assert "private-" not in response.text
    async with factory() as check:
        assert await check.scalar(select(func.count()).select_from(Vacancy)) == 0


async def test_collection_commit_failure_is_not_reported_as_success(
    async_client, collection_api, sqlite_session, monkeypatch
):
    service, _, _, factory = collection_api

    async def collect(*args):
        sqlite_session.add(Vacancy(**asdict(make_vacancy_data())))
        await sqlite_session.flush()
        return CollectionRunProgressResponse(
            created=1, updated=0, skipped=0, failed=0, next_page=1, exhausted=False
        )

    service.collect_pages_with_progress.side_effect = collect
    monkeypatch.setattr(
        sqlite_session, "commit", AsyncMock(side_effect=SQLAlchemyError("private-sql"))
    )
    response = await async_client.post(ENDPOINT, json=BODY)
    assert response.status_code == 500
    assert "private-sql" not in response.text
    async with factory() as check:
        assert await check.scalar(select(func.count()).select_from(Vacancy)) == 0


async def test_collection_cancellation_rolls_back_without_success(
    async_client, collection_api, sqlite_session
):
    service, _, _, factory = collection_api

    async def collect(*args):
        sqlite_session.add(Vacancy(**asdict(make_vacancy_data())))
        await sqlite_session.flush()
        raise asyncio.CancelledError

    service.collect_pages_with_progress.side_effect = collect
    with pytest.raises(asyncio.CancelledError):
        await async_client.post(ENDPOINT, json=BODY)
    async with factory() as check:
        assert await check.scalar(select(func.count()).select_from(Vacancy)) == 0
