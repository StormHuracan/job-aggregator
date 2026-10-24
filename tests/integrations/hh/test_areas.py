from unittest.mock import AsyncMock

import pytest

from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.errors import HHPermanentRequestError


async def test_area_suggestions_normalize_names_and_drop_external_urls():
    api = AsyncMock()
    api.request.return_value = {
        "items": [
            {
                "id": "1",
                "text": "Москва",
                "url": "https://hh.ru/area/1",
                "parent": {"id": "113", "text": "Россия"},
            },
            {"id": "2", "text": "Санкт-Петербург", "url": "https://hh.ru/area/2"},
        ]
    }
    areas = await HHClient(api).suggest_areas("Мос")
    assert [area.model_dump() for area in areas] == [
        {"id": "1", "name": "Москва", "parent_name": "Россия"},
        {"id": "2", "name": "Санкт-Петербург", "parent_name": None},
    ]
    api.request.assert_awaited_once_with("GET", "/suggests/areas", {"text": "Мос"})


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"items": "secret"},
        {"items": [None]},
        {"items": [{"id": 1, "text": "Москва"}]},
        {"items": [{"id": "1", "text": ""}]},
    ],
)
async def test_invalid_area_response_is_a_safe_integration_error(response):
    api = AsyncMock()
    api.request.return_value = response
    with pytest.raises(HHPermanentRequestError):
        await HHClient(api).suggest_areas("Москва")


async def test_empty_area_results_are_valid():
    api = AsyncMock()
    api.request.return_value = {"items": []}
    assert await HHClient(api).suggest_areas("НетТакогоРегиона") == []
