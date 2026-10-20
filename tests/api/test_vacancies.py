from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import SESSION_COOKIE_NAME
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.schemas.vacancy import VacancyResponse
from job_aggregator.services.auth_sessions import AuthSessionService
from tests.factories import make_vacancy_data

ENDPOINT = "/vacancies"


@pytest.fixture
async def api_client(
    app: FastAPI,
    sqlite_session: AsyncSession,
    async_client: AsyncClient,
) -> Any:
    async def override_get_db() -> Any:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_get_db
    yield async_client
    app.dependency_overrides.clear()


async def _authorize(
    session: AsyncSession,
    client: AsyncClient,
    hh_user_id: str = "hh-1",
) -> None:
    user = User(hh_user_id=hh_user_id, display_name="Test User")
    session.add(user)
    await session.commit()
    token = await AuthSessionService(session).create_session(user.id)
    await session.commit()
    client.cookies.set(SESSION_COOKIE_NAME, token)


async def _save(session: AsyncSession, **overrides: Any) -> None:
    await VacancyRepository(session).upsert(make_vacancy_data(**overrides))
    await session.commit()


def _params(**extra: Any) -> dict[str, Any]:
    return {"limit": 20, "offset": 0, **extra}


async def test_missing_session_returns_401(api_client: AsyncClient) -> None:
    response = await api_client.get(ENDPOINT, params=_params())

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_authorized_users_see_the_same_vacancies(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _save(sqlite_session, external_id="1", title="Python")
    await _authorize(sqlite_session, api_client, "hh-1")
    first = await api_client.get(ENDPOINT, params=_params())

    await _authorize(sqlite_session, api_client, "hh-2")
    second = await api_client.get(ENDPOINT, params=_params())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["total"] == 1


async def test_empty_database_returns_empty_page(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)

    response = await api_client.get(ENDPOINT, params=_params())

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


async def test_offset_past_the_end_keeps_total(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(sqlite_session, external_id="1")
    await _save(sqlite_session, external_id="2")

    response = await api_client.get(ENDPOINT, params=_params(offset=10))

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 20
    assert response.json()["offset"] == 10


async def test_company_filter_is_case_insensitive_substring(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(sqlite_session, external_id="1", company_name="ACME Corp")
    await _save(sqlite_session, external_id="2", company_name="Other")

    response = await api_client.get(ENDPOINT, params=_params(company="acme"))

    body = response.json()
    assert response.status_code == 200
    assert [item["external_id"] for item in body["items"]] == ["1"]
    assert body["total"] == 1


async def test_area_filter_is_case_insensitive_substring(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(sqlite_session, external_id="1", area_name="Saint Petersburg")
    await _save(sqlite_session, external_id="2", area_name="Moscow")

    response = await api_client.get(ENDPOINT, params=_params(area="petersburg"))

    body = response.json()
    assert response.status_code == 200
    assert [item["external_id"] for item in body["items"]] == ["1"]
    assert body["total"] == 1


async def test_text_filter_matches_title_or_description(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(
        sqlite_session,
        external_id="1",
        title="Python Developer",
        description="Backend",
    )
    await _save(
        sqlite_session,
        external_id="2",
        title="Engineer",
        description="We use PYTHON",
    )
    await _save(sqlite_session, external_id="3", title="Designer", description="Figma")

    response = await api_client.get(ENDPOINT, params=_params(text="python"))

    body = response.json()
    assert response.status_code == 200
    assert sorted(item["external_id"] for item in body["items"]) == ["1", "2"]
    assert body["total"] == 2


async def test_salary_from_excludes_null(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(sqlite_session, external_id="1", salary_from=150_000)
    await _save(sqlite_session, external_id="2", salary_from=50_000)
    await _save(sqlite_session, external_id="3", salary_from=None)

    response = await api_client.get(ENDPOINT, params=_params(salary_from=100_000))

    body = response.json()
    assert response.status_code == 200
    assert [item["external_id"] for item in body["items"]] == ["1"]
    assert body["total"] == 1


async def test_salary_to_excludes_null(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(sqlite_session, external_id="1", salary_to=150_000)
    await _save(sqlite_session, external_id="2", salary_to=250_000)
    await _save(sqlite_session, external_id="3", salary_to=None)

    response = await api_client.get(ENDPOINT, params=_params(salary_to=200_000))

    body = response.json()
    assert response.status_code == 200
    assert [item["external_id"] for item in body["items"]] == ["1"]
    assert body["total"] == 1


async def test_filters_are_combined_with_and(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(
        sqlite_session, external_id="1", company_name="Acme", area_name="Moscow"
    )
    await _save(sqlite_session, external_id="2", company_name="Acme", area_name="Kazan")
    await _save(
        sqlite_session, external_id="3", company_name="Other", area_name="Moscow"
    )

    response = await api_client.get(
        ENDPOINT, params=_params(company="acme", area="moscow")
    )

    body = response.json()
    assert response.status_code == 200
    assert [item["external_id"] for item in body["items"]] == ["1"]
    assert body["total"] == 1


async def test_sort_is_published_at_desc_nulls_last_then_id(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    jan_2 = datetime(2026, 1, 2, tzinfo=UTC)
    await _save(sqlite_session, external_id="a", published_at=jan_2)
    await _save(sqlite_session, external_id="b", published_at=None)
    await _save(
        sqlite_session,
        external_id="c",
        published_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    await _save(sqlite_session, external_id="d", published_at=jan_2)

    response = await api_client.get(ENDPOINT, params=_params())

    assert response.status_code == 200
    assert [item["external_id"] for item in response.json()["items"]] == [
        "c",
        "a",
        "d",
        "b",
    ]


async def test_total_is_counted_before_pagination(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    for day in range(1, 6):
        await _save(
            sqlite_session,
            external_id=str(day),
            published_at=datetime(2026, 1, day, tzinfo=UTC),
        )

    response = await api_client.get(ENDPOINT, params=_params(limit=2, offset=2))

    body = response.json()
    assert response.status_code == 200
    assert [item["external_id"] for item in body["items"]] == ["3", "2"]
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 2


async def test_response_hides_raw_data_and_secrets(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
) -> None:
    await _authorize(sqlite_session, api_client)
    await _save(
        sqlite_session,
        external_id="1",
        raw_data={"access_token": "ACCESS-SECRET", "refresh_token": "REFRESH-SECRET"},
    )

    response = await api_client.get(ENDPOINT, params=_params())

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == set(VacancyResponse.model_fields)
    assert "raw_data" not in item
    assert "ACCESS-SECRET" not in response.text
    assert "REFRESH-SECRET" not in response.text


@pytest.mark.parametrize(
    "params",
    [
        {"offset": 0},
        {"limit": 20},
        {"limit": 0, "offset": 0},
        {"limit": 101, "offset": 0},
        {"limit": 20, "offset": -1},
        {"limit": 20, "offset": 0, "salary_from": -1},
        {"limit": 20, "offset": 0, "salary_to": -1},
        {"limit": 20, "offset": 0, "salary_from": 200, "salary_to": 100},
    ],
)
async def test_invalid_query_returns_422(
    api_client: AsyncClient,
    sqlite_session: AsyncSession,
    params: dict[str, int],
) -> None:
    await _authorize(sqlite_session, api_client)

    response = await api_client.get(ENDPOINT, params=params)

    assert response.status_code == 422
