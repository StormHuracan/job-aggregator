from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.user import User
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHPermanentRequestError,
    HHTemporaryError,
)


async def test_area_search_requires_session(app, async_client):
    app.dependency_overrides[get_db_session] = lambda: AsyncMock(spec=AsyncSession)
    assert (await async_client.get("/hh/areas?text=Мос")).status_code == 401


@pytest.fixture
def areas_api(app):
    from job_aggregator.api.hh_areas import get_hh_area_client
    from job_aggregator.schemas.hh_area import HHAreaSuggestion

    app.dependency_overrides[get_current_user] = lambda: User(
        id=42, hh_user_id="42", display_name="Тест"
    )
    client = AsyncMock()
    client.suggest_areas.return_value = [
        HHAreaSuggestion(id="1", name="Москва", parent_name="Россия")
    ]
    app.dependency_overrides[get_hh_area_client] = lambda: client
    return client


async def test_area_search_returns_only_public_suggestions(async_client, areas_api):
    response = await async_client.get("/hh/areas", params={"text": " Мос "})
    assert response.status_code == 200
    assert response.json() == [{"id": "1", "name": "Москва", "parent_name": "Россия"}]
    areas_api.suggest_areas.assert_awaited_once_with("Мос")


@pytest.mark.parametrize("text", ["", "а", "   ", "а" * 256])
async def test_invalid_area_query_does_not_call_hh(async_client, areas_api, text):
    assert (
        await async_client.get("/hh/areas", params={"text": text})
    ).status_code == 422
    areas_api.suggest_areas.assert_not_awaited()


@pytest.mark.parametrize(
    "error,status",
    [
        (HHAuthenticationError("secret"), 409),
        (HHTemporaryError("secret"), 503),
        (HHPermanentRequestError("secret"), 502),
    ],
)
async def test_area_errors_do_not_expose_hh_payload(
    async_client, areas_api, error, status
):
    areas_api.suggest_areas.side_effect = error
    response = await async_client.get("/hh/areas?text=Мос")
    assert response.status_code == status
    assert "secret" not in response.text


async def test_area_client_is_authorized_for_session_owner_not_query_user(
    app, async_client, monkeypatch
):
    app.dependency_overrides[get_current_user] = lambda: User(
        id=42, hh_user_id="42", display_name="Тест"
    )
    app.state.session_factory = object()
    api = AsyncMock()
    api.request.return_value = {"items": [{"id": "1", "text": "Москва"}]}
    factory = Mock(return_value=api)
    monkeypatch.setattr("job_aggregator.api.hh_areas.AuthorizedHHAPIClient", factory)
    response = await async_client.get(
        "/hh/areas", params={"text": "Мос", "user_id": 999}
    )
    assert response.status_code == 200
    assert factory.call_args.kwargs["user_id"] == 42
    assert factory.call_args.kwargs["session_factory"] is app.state.session_factory
    api.request.assert_awaited_once_with("GET", "/suggests/areas", {"text": "Мос"})
