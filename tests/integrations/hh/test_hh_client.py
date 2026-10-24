from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from hh_applicant_tool import api as hh_api
from hh_applicant_tool.api import errors as hh_errors
from requests import Response

from job_aggregator.integrations.hh.client import (
    HHAPIClient,
    HHClient,
    HHOAuthClient,
)
from job_aggregator.integrations.hh.dto import HHVacancySearchParams
from job_aggregator.integrations.hh.errors import (
    HHIntegrationError,
    HHPermanentRequestError,
)
from job_aggregator.schemas.hh_token import HHAccountTokenData


class _StubApiClient:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.calls: list[tuple[str, str, dict | None]] = []

    async def request(
        self, method: str, endpoint: str, params: dict | None = None
    ) -> Any:
        self.calls.append((method, endpoint, params))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _item(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "12345",
        "name": "Python Developer",
        "alternate_url": "https://hh.ru/vacancy/12345",
        "employer": {"name": "Acme"},
        "area": {"name": "Москва"},
        "salary": {"from": 100_000, "to": 200_000, "currency": "RUR"},
        "snippet": {"responsibility": "Описание"},
        "published_at": "2026-01-01T12:00:00+0300",
    }
    base.update(overrides)
    return base


async def test_search_vacancies_success() -> None:
    stub = _StubApiClient(
        {
            "items": [_item(), _item(id="999", name="Second")],
            "page": 0,
            "found": 2,
            "pages": 1,
        }
    )
    client = HHClient(stub)  # type: ignore[arg-type]

    page = await client.search_vacancies(HHVacancySearchParams(text="python"))

    assert page.page == 0
    assert page.found == 2
    assert page.pages == 1
    assert len(page.items) == 2

    first = page.items[0]
    assert first.source == "hh"
    assert first.external_id == "12345"
    assert first.title == "Python Developer"
    assert first.company_name == "Acme"
    assert first.area_name == "Москва"
    assert first.salary_from == 100_000
    assert first.salary_to == 200_000
    assert first.salary_currency == "RUR"
    assert first.description == "Описание"
    assert first.source_url == "https://hh.ru/vacancy/12345"
    assert first.published_at == datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    assert first.raw_data is not None


async def test_search_vacancies_sends_expected_query() -> None:
    stub = _StubApiClient({"items": [], "page": 0, "found": 0, "pages": 0})
    client = HHClient(stub)  # type: ignore[arg-type]

    await client.search_vacancies(
        HHVacancySearchParams(text="python", area="1", page=2, per_page=50)
    )

    assert stub.calls == [
        (
            "GET",
            "/vacancies",
            {"text": "python", "page": 2, "per_page": 50, "area": "1"},
        )
    ]


async def test_search_vacancies_omits_area_when_absent() -> None:
    stub = _StubApiClient({"items": [], "page": 0, "found": 0, "pages": 0})
    client = HHClient(stub)  # type: ignore[arg-type]

    await client.search_vacancies(HHVacancySearchParams(text="python"))

    _, _, params = stub.calls[0]
    assert params is not None
    assert "area" not in params


async def test_search_vacancies_empty_page() -> None:
    stub = _StubApiClient({"items": [], "page": 0, "found": 0, "pages": 0})
    client = HHClient(stub)  # type: ignore[arg-type]

    page = await client.search_vacancies(HHVacancySearchParams(text="python"))

    assert page.items == []
    assert page.page == 0
    assert page.found == 0
    assert page.pages == 0


async def test_search_vacancies_partial_fields_become_none() -> None:
    item = _item()
    del item["salary"]
    del item["area"]
    del item["snippet"]
    del item["published_at"]

    stub = _StubApiClient({"items": [item], "page": 0, "found": 1, "pages": 1})
    client = HHClient(stub)  # type: ignore[arg-type]

    page = await client.search_vacancies(HHVacancySearchParams(text="python"))

    assert len(page.items) == 1
    vacancy = page.items[0]
    assert vacancy.salary_from is None
    assert vacancy.salary_to is None
    assert vacancy.salary_currency is None
    assert vacancy.area_name is None
    assert vacancy.description is None
    assert vacancy.published_at is None


async def test_search_vacancies_skips_item_without_required_fields() -> None:
    bad = _item()
    del bad["id"]
    stub = _StubApiClient(
        {
            "items": [bad, _item(id="777")],
            "page": 0,
            "found": 2,
            "pages": 1,
        }
    )
    client = HHClient(stub)  # type: ignore[arg-type]

    page = await client.search_vacancies(HHVacancySearchParams(text="python"))

    assert len(page.items) == 1
    assert page.items[0].external_id == "777"


async def test_search_vacancies_naive_published_at_is_none() -> None:
    item = _item(published_at="2026-01-01T12:00:00")
    stub = _StubApiClient({"items": [item], "page": 0, "found": 1, "pages": 1})
    client = HHClient(stub)  # type: ignore[arg-type]

    page = await client.search_vacancies(HHVacancySearchParams(text="python"))

    assert page.items[0].published_at is None


async def test_search_vacancies_published_at_other_timezone_to_utc() -> None:
    tz = timezone(timedelta(hours=3))
    source = datetime(2026, 1, 1, 12, 0, tzinfo=tz)
    item = _item(published_at=source.isoformat())
    stub = _StubApiClient({"items": [item], "page": 0, "found": 1, "pages": 1})
    client = HHClient(stub)  # type: ignore[arg-type]

    page = await client.search_vacancies(HHVacancySearchParams(text="python"))

    assert page.items[0].published_at == datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


async def test_search_vacancies_wraps_unexpected_response() -> None:
    stub = _StubApiClient({"unexpected": "structure"})
    client = HHClient(stub)  # type: ignore[arg-type]

    with pytest.raises(HHPermanentRequestError):
        await client.search_vacancies(HHVacancySearchParams(text="python"))


async def test_search_vacancies_items_not_list_raises() -> None:
    stub = _StubApiClient({"items": "not-a-list", "page": 0, "found": 0, "pages": 0})
    client = HHClient(stub)  # type: ignore[arg-type]

    with pytest.raises(HHIntegrationError):
        await client.search_vacancies(HHVacancySearchParams(text="python"))


async def test_search_vacancies_invalid_metadata_raises() -> None:
    stub = _StubApiClient({"items": [], "page": 0, "found": 0, "pages": -1})
    client = HHClient(stub)  # type: ignore[arg-type]

    with pytest.raises(HHIntegrationError):
        await client.search_vacancies(HHVacancySearchParams(text="python"))


async def test_get_authorization_url():
    state = "example"
    client = HHOAuthClient(client_id="12234", client_secret="23455")
    response = client.get_authorization_url("https://234.ru", state)
    query = urlparse(response).query
    res = parse_qs(query)
    assert res["state"] == [state]
    assert res["client_id"] == ["12234"]


async def test_search_vacancies_retries_rate_limit(monkeypatch):
    delays = []
    calls = []

    async def record_sleep(seconds: float) -> None:
        delays.append(seconds)

    class FakeApiClient:
        def __init__(self, **kwargs):
            pass

        def request(self, method, endpoint, params=None):
            calls.append((method, endpoint, params))

            if len(calls) == 1:
                response = Response()
                response.status_code = 429
                raise hh_errors.LimitExceeded(
                    response,
                    {"errors": [{"type": "limit_exceeded", "value": "private"}]},
                )

            return {
                "items": [],
                "page": 2,
                "found": 0,
                "pages": 0,
            }

        def get_access_token(self):
            return {
                "access_token": "test-access",
                "refresh_token": "test-refresh",
                "access_expires_at": 1893456000,
            }

    monkeypatch.setattr(hh_api, "ApiClient", FakeApiClient)

    tokens = HHAccountTokenData(
        access_token="test-access",
        refresh_token="test-refresh",
        access_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    api_client = HHAPIClient(
        tokens,
        allow_token_refresh=False,
        retry_sleep=record_sleep,
    )
    client = HHClient(api_client)

    try:
        params = HHVacancySearchParams(
            text="Python",
            area="1",
            page=2,
            per_page=50,
        )

        result = await client.search_vacancies(params)

        assert result.page == 2
        assert result.items == []
        assert len(calls) == 2
        assert calls[0] == calls[1]
        assert calls[0] == (
            "GET",
            "/vacancies",
            {"text": "Python", "page": 2, "per_page": 50, "area": "1"},
        )
        assert delays == [0.5]
    finally:
        api_client.close()
