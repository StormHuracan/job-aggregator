from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.api.dependencies import SESSION_COOKIE_NAME
from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.saved_search_match import SavedSearchMatchRepository
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService
from tests.factories import make_vacancy_data


@pytest.fixture
async def matches_api(
    app: FastAPI, sqlite_session: AsyncSession, async_client: AsyncClient
) -> tuple[int, int]:
    """Реальные сессии пользователей, отдельная DB-сессия на каждый HTTP-запрос."""
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)

    async def database() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = database
    owner = User(hh_user_id="matches-owner", display_name="Owner")
    other = User(hh_user_id="matches-other", display_name="Other")
    sqlite_session.add_all([owner, other])
    await sqlite_session.flush()
    token = await AuthSessionService(sqlite_session).create_session(owner.id)
    await sqlite_session.commit()
    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    return owner.id, other.id


async def _seed_matches(session: AsyncSession, owner_id: int, other_id: int) -> None:
    await VacancyRepository(session).upsert(make_vacancy_data())
    vacancy_id = await session.scalar(select(Vacancy.id))
    # Две связи одной общей вакансии считаются как два совпадения владельца.
    for index, user_id in enumerate((owner_id, owner_id, owner_id, other_id, None)):
        search = SavedSearch(name=f"Search {index}", text="python", user_id=user_id)
        session.add(search)
        await session.flush()
        session.add(
            SavedSearchMatch(
                saved_search_id=search.id,
                vacancy_id=vacancy_id,
                matched_at=datetime(2026, 10, 1, tzinfo=UTC),
                seen_at=datetime(2026, 10, 2, tzinfo=UTC) if index == 2 else None,
            )
        )
    await session.commit()


async def test_profile_returns_zero_when_no_matches(
    matches_api: tuple[int, int], async_client: AsyncClient
) -> None:
    response = await async_client.get("/me")

    assert response.status_code == 200
    assert response.json()["new_matches_count"] == 0
    assert response.headers["Cache-Control"] == "no-store"


async def test_profile_counts_only_unseen_matches_of_current_user(
    matches_api: tuple[int, int],
    sqlite_session: AsyncSession,
    async_client: AsyncClient,
) -> None:
    owner_id, other_id = matches_api
    await _seed_matches(sqlite_session, owner_id, other_id)

    response = await async_client.get("/me")

    assert response.status_code == 200
    assert response.json()["new_matches_count"] == 2


async def test_mark_seen_persists_only_current_user_matches_and_is_repeatable(
    matches_api: tuple[int, int],
    sqlite_session: AsyncSession,
    async_client: AsyncClient,
) -> None:
    owner_id, other_id = matches_api
    await _seed_matches(sqlite_session, owner_id, other_id)
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)

    response = await async_client.post("/me/matches/mark-seen")

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    async with factory() as session:
        seen_after_first = dict(
            (
                await session.execute(
                    select(SavedSearchMatch.id, SavedSearchMatch.seen_at)
                )
            ).all()
        )
        repository = SavedSearchMatchRepository(session)
        assert await repository.count_unseen_for_user(owner_id) == 0
        assert await repository.count_unseen_for_user(other_id) == 1
        legacy_unseen = await session.scalar(
            select(SavedSearchMatch.id)
            .join(SavedSearch)
            .where(SavedSearch.user_id.is_(None), SavedSearchMatch.seen_at.is_(None))
        )
        assert legacy_unseen is not None
        old_seen = datetime(2026, 10, 2)
        assert old_seen in seen_after_first.values()

    repeated = await async_client.post("/me/matches/mark-seen")
    assert repeated.status_code == 204
    assert (await async_client.get("/me")).json()["new_matches_count"] == 0
    async with factory() as session:
        seen_after_repeat = dict(
            (
                await session.execute(
                    select(SavedSearchMatch.id, SavedSearchMatch.seen_at)
                )
            ).all()
        )
        assert seen_after_repeat == seen_after_first


@pytest.mark.parametrize(
    "method,path", [("GET", "/me"), ("POST", "/me/matches/mark-seen")]
)
async def test_match_endpoints_require_session(
    matches_api: tuple[int, int], method: str, path: str, async_client: AsyncClient
) -> None:
    async_client.cookies.clear()
    assert (await async_client.request(method, path)).status_code == 401


@pytest.mark.parametrize(
    "method,path", [("GET", "/me"), ("POST", "/me/matches/mark-seen")]
)
async def test_match_endpoints_handle_commit_failure_without_saving_changes(
    matches_api: tuple[int, int],
    sqlite_session: AsyncSession,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    owner_id, other_id = matches_api
    await _seed_matches(sqlite_session, owner_id, other_id)

    async def failing_commit(self: AsyncSession) -> None:
        raise SQLAlchemyError("private-database-details")

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    response = await async_client.request(method, path)

    assert response.status_code == 500
    assert "private-database-details" not in response.text
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)
    async with factory() as session:
        assert (
            await SavedSearchMatchRepository(session).count_unseen_for_user(owner_id)
            == 2
        )


@pytest.mark.parametrize(
    "method,path,repository_method",
    [
        ("GET", "/me", "count_unseen_for_user"),
        ("POST", "/me/matches/mark-seen", "mark_seen_for_user"),
    ],
)
async def test_match_endpoints_hide_storage_errors(
    matches_api: tuple[int, int],
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    repository_method: str,
) -> None:
    async def fail(self: SavedSearchMatchRepository, user_id: int) -> int:
        raise SQLAlchemyError("private-database-details")

    monkeypatch.setattr(SavedSearchMatchRepository, repository_method, fail)
    response = await async_client.request(method, path)

    assert response.status_code == 500
    assert "private-database-details" not in response.text
