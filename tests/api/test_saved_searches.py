from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService

SESSION_COOKIE_NAME = "job_aggregator_session"


async def test_delete_search_is_owner_scoped(
    async_client: AsyncClient, api_session_override, sqlite_session: AsyncSession
) -> None:
    _, token_a = await _create_user_and_token(sqlite_session, "delete-a")
    _, token_b = await _create_user_and_token(sqlite_session, "delete-b")
    async_client.cookies.set(SESSION_COOKIE_NAME, token_a)
    created = await async_client.post(
        "/saved-searches", json={"name": "Python", "text": "backend"}
    )
    path = f"/saved-searches/{created.json()['id']}"
    vacancy = Vacancy(
        external_id="delete-test",
        title="Backend",
        company_name="Company",
        source_url="https://hh.ru/vacancy/delete-test",
    )
    sqlite_session.add(vacancy)
    await sqlite_session.flush()
    sqlite_session.add(
        SavedSearchMatch(
            saved_search_id=created.json()["id"],
            vacancy_id=vacancy.id,
            matched_at=datetime.now(UTC),
        )
    )
    await sqlite_session.commit()
    async_client.cookies.set(SESSION_COOKIE_NAME, token_b)
    assert (await async_client.delete(path)).status_code == 404
    async_client.cookies.set(SESSION_COOKIE_NAME, token_a)
    assert (await async_client.delete(path)).status_code == 204
    assert (await async_client.get("/saved-searches")).json() == []
    assert (await async_client.get("/me")).json()["new_matches_count"] == 0
    remaining = await async_client.get("/vacancies?limit=20&offset=0")
    assert remaining.json()["items"][0]["external_id"] == "delete-test"
    assert (await async_client.delete(path)).status_code == 404
    async_client.cookies.clear()
    assert (await async_client.delete(path)).status_code == 401


async def _create_user_and_token(session: AsyncSession, label: str) -> tuple[User, str]:
    user = User(hh_user_id=f"hh-{label}", display_name=label)
    session.add(user)
    await session.flush()
    token = await AuthSessionService(session).create_session(user.id)
    await session.commit()
    return user, token


@pytest.fixture
async def api_session_override(app, sqlite_session: AsyncSession):
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = override_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_saved_search_endpoints_require_valid_session(
    async_client: AsyncClient, api_session_override
) -> None:
    response = await async_client.get("/saved-searches")
    assert response.status_code == 401

    async_client.cookies.set(SESSION_COOKIE_NAME, "invalid-token")
    response = await async_client.get("/saved-searches")
    assert response.status_code == 401


async def test_create_and_list_saved_searches_are_user_scoped(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
) -> None:
    _, token_a = await _create_user_and_token(sqlite_session, "a")
    _, token_b = await _create_user_and_token(sqlite_session, "b")

    async_client.cookies.set(SESSION_COOKIE_NAME, token_a)
    created = await async_client.post(
        "/saved-searches",
        json={
            "name": "  Python  ",
            "text": "  backend developer  ",
            "area": " Minsk ",
            "min_salary": 1000,
            "max_salary": 5000,
        },
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Python"
    assert created.json()["text"] == "backend developer"
    assert created.json()["area"] == "Minsk"
    assert created.json()["is_enabled"] is True

    listed_a = await async_client.get("/saved-searches")
    assert [item["id"] for item in listed_a.json()] == [created.json()["id"]]

    async_client.cookies.set(SESSION_COOKIE_NAME, token_b)
    listed_b = await async_client.get("/saved-searches")
    assert listed_b.status_code == 200
    assert listed_b.json() == []


async def test_patch_changes_only_own_search_and_hides_other_users_search(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
) -> None:
    _, token_a = await _create_user_and_token(sqlite_session, "patch-a")
    _, token_b = await _create_user_and_token(sqlite_session, "patch-b")

    async_client.cookies.set(SESSION_COOKIE_NAME, token_a)
    created = await async_client.post(
        "/saved-searches", json={"name": "Python", "text": "backend"}
    )
    search_id = created.json()["id"]

    updated = await async_client.patch(
        f"/saved-searches/{search_id}", json={"is_enabled": False}
    )
    assert updated.status_code == 200
    assert updated.json()["is_enabled"] is False
    assert updated.json()["name"] == "Python"

    async_client.cookies.set(SESSION_COOKIE_NAME, token_b)
    hidden = await async_client.patch(
        f"/saved-searches/{search_id}", json={"is_enabled": True}
    )
    assert hidden.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "text": "backend"},
        {"name": "Python", "text": "   "},
        {"name": "x" * 256, "text": "backend"},
        {"name": "Python", "text": "x" * 256},
        {"name": "Python", "text": "backend", "area": "x" * 256},
        {"name": "Python", "text": "backend", "min_salary": -1},
        {"name": "Python", "text": "backend", "max_salary": -1},
        {
            "name": "Python",
            "text": "backend",
            "min_salary": 5000,
            "max_salary": 1000,
        },
        {"name": "Python", "text": "backend", "user_id": 123},
    ],
)
async def test_create_rejects_invalid_payloads(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
    payload: dict[str, object],
) -> None:
    _, token = await _create_user_and_token(sqlite_session, "validation")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)

    response = await async_client.post("/saved-searches", json=payload)
    assert response.status_code == 422


async def test_patch_rejects_extra_fields(
    async_client: AsyncClient,
    api_session_override,
    sqlite_session: AsyncSession,
) -> None:
    _, token = await _create_user_and_token(sqlite_session, "patch-validation")
    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.patch(
        "/saved-searches/1", json={"is_enabled": False, "name": "changed"}
    )
    assert response.status_code == 422
