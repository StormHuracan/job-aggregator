import pytest

from job_aggregator.integrations.hh.dto import (
    HHVacancyPage,
    HHVacancySearchParams,
)
from tests.fakes.hh import FakeHHClient


async def test_search_vacancies_returns_requested_page():
    page = HHVacancyPage(
        items=[],
        page=0,
        found=0,
        pages=0,
    )

    client = FakeHHClient(pages={0: page})
    params = HHVacancySearchParams(text="Python", page=0)

    result = await client.search_vacancies(params)
    assert result == page
    assert client.calls == [params]


async def test_search_vacancies_raises_error_for_missing_page():
    page = HHVacancyPage(
        items=[],
        page=0,
        found=0,
        pages=0,
    )

    client = FakeHHClient(pages={0: page})
    params = HHVacancySearchParams(text="Python", page=1)

    with pytest.raises(ValueError):
        await client.search_vacancies(params)


async def test_search_vacancies_raises_configured_error():
    page = HHVacancyPage(
        items=[],
        page=0,
        found=0,
        pages=0,
    )

    error = RuntimeError("Ошибка HH API")

    client = FakeHHClient(pages={0: page}, error=error)
    params = HHVacancySearchParams(text="Python", page=0)

    with pytest.raises(RuntimeError, match="Ошибка HH API"):
        await client.search_vacancies(params)

    assert client.calls == [params]


async def test_clients_have_independent_call_history():
    page = HHVacancyPage(
        items=[],
        page=0,
        found=0,
        pages=0,
    )

    first_client = FakeHHClient(pages={0: page})
    second_client = FakeHHClient(pages={0: page})
    params = HHVacancySearchParams(text="Python", page=0)

    await first_client.search_vacancies(params)

    assert first_client.calls == [params]
    assert second_client.calls == []
