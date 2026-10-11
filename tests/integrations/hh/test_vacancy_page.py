from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from job_aggregator.integrations.hh import HHVacancyPage
from job_aggregator.schemas.vacancy import VacancyData


@pytest.fixture
def vacancy() -> VacancyData:
    return VacancyData(
        source="hh",
        external_id="123",
        title="Python developer",
        company_name="Example",
        area_name=None,
        salary_from=None,
        salary_to=None,
        salary_currency=None,
        description=None,
        source_url="https://hh.ru/vacancy/123",
        published_at=datetime(2026, 10, 11, tzinfo=UTC),
        raw_data=None,
    )


def test_empty_page() -> None:
    page = HHVacancyPage(items=[], page=0, found=0, pages=0)

    assert page.items == []
    assert page.page == 0
    assert page.found == 0
    assert page.pages == 0


def test_page_with_normalized_vacancy(vacancy: VacancyData) -> None:
    page = HHVacancyPage(items=[vacancy], page=1, found=42, pages=3)

    assert len(page.items) == 1
    assert isinstance(page.items[0], VacancyData)
    assert page.items[0] == vacancy
    assert page.page == 1
    assert page.found == 42
    assert page.pages == 3


@pytest.mark.parametrize("field", ["page", "found", "pages"])
def test_page_rejects_negative_numbers(field: str) -> None:
    values = {"page": 0, "found": 0, "pages": 0}
    values[field] = -1

    with pytest.raises(ValidationError) as error:
        HHVacancyPage(items=[], **values)

    assert error.value.errors()[0]["loc"] == (field,)


def test_page_requires_all_fields() -> None:
    with pytest.raises(ValidationError) as error:
        HHVacancyPage()  # type: ignore[call-arg]

    assert {item["loc"] for item in error.value.errors()} == {
        ("items",),
        ("page",),
        ("found",),
        ("pages",),
    }


def test_page_rejects_raw_hh_response() -> None:
    with pytest.raises(ValidationError):
        HHVacancyPage(
            items=[{"id": "123", "name": "Python developer"}], page=0, found=1, pages=1
        )


def test_page_items_are_independent(vacancy: VacancyData) -> None:
    items = [vacancy]
    first = HHVacancyPage(items=items, page=0, found=1, pages=1)
    second = HHVacancyPage(items=items, page=0, found=1, pages=1)

    first.items.clear()

    assert second.items == [vacancy]
    assert items == [vacancy]
