from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.saved_search_match import SavedSearchMatchRepository
from job_aggregator.db.repositories.vacancy import VacancyRepository
from tests.factories import make_vacancy_data

SEEN_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def _user(session: AsyncSession, hh_user_id: str) -> User:
    user = User(hh_user_id=hh_user_id, display_name="Test User")
    session.add(user)
    await session.flush()
    return user


async def _search(
    session: AsyncSession, *, name: str, user_id: int | None
) -> SavedSearch:
    search = SavedSearch(name=name, text="python", user_id=user_id)
    session.add(search)
    await session.flush()
    return search


async def _vacancy(session: AsyncSession, external_id: str) -> Vacancy:
    await VacancyRepository(session).upsert(make_vacancy_data(external_id=external_id))
    vacancy = await session.scalar(
        select(Vacancy).where(Vacancy.external_id == external_id)
    )
    assert vacancy is not None
    return vacancy


async def test_record_creates_pair_once(sqlite_session: AsyncSession) -> None:
    user = await _user(sqlite_session, "hh-1")
    search = await _search(sqlite_session, name="Python", user_id=user.id)
    vacancy = await _vacancy(sqlite_session, "1")
    repo = SavedSearchMatchRepository(sqlite_session)

    assert await repo.record(search.id, vacancy.id) is True
    match = await sqlite_session.scalar(select(SavedSearchMatch))
    assert match is not None
    matched_at = match.matched_at

    assert await repo.record(search.id, vacancy.id) is False
    await sqlite_session.refresh(match)
    assert match.matched_at == matched_at
    assert match.seen_at is None


async def test_repeat_keeps_seen_at(sqlite_session: AsyncSession) -> None:
    user = await _user(sqlite_session, "hh-1")
    search = await _search(sqlite_session, name="Python", user_id=user.id)
    vacancy = await _vacancy(sqlite_session, "1")
    repo = SavedSearchMatchRepository(sqlite_session)
    await repo.record(search.id, vacancy.id)
    match = await sqlite_session.scalar(select(SavedSearchMatch))
    assert match is not None
    match.seen_at = SEEN_AT
    await sqlite_session.flush()

    assert await repo.record(search.id, vacancy.id) is False
    await sqlite_session.refresh(match)
    assert match.seen_at.replace(tzinfo=UTC) == SEEN_AT


async def test_rollback_removes_recorded_match(sqlite_session: AsyncSession) -> None:
    user = await _user(sqlite_session, "hh-1")
    search = await _search(sqlite_session, name="Python", user_id=user.id)
    vacancy = await _vacancy(sqlite_session, "1")
    repo = SavedSearchMatchRepository(sqlite_session)

    assert await repo.record(search.id, vacancy.id) is True
    await sqlite_session.rollback()

    assert await repo.count_unseen_for_user(user.id) == 0


async def test_repeat_leaves_session_usable(sqlite_session: AsyncSession) -> None:
    user = await _user(sqlite_session, "hh-1")
    search = await _search(sqlite_session, name="Python", user_id=user.id)
    first = await _vacancy(sqlite_session, "1")
    second = await _vacancy(sqlite_session, "2")
    repo = SavedSearchMatchRepository(sqlite_session)

    assert await repo.record(search.id, first.id) is True
    assert await repo.record(search.id, first.id) is False
    assert await repo.record(search.id, second.id) is True
    assert await repo.count_unseen_for_user(user.id) == 2


async def test_unseen_count_is_isolated_by_owner(
    sqlite_session: AsyncSession,
) -> None:
    owner = await _user(sqlite_session, "hh-1")
    other = await _user(sqlite_session, "hh-2")
    own_search = await _search(sqlite_session, name="Own", user_id=owner.id)
    other_search = await _search(sqlite_session, name="Other", user_id=other.id)
    legacy = await _search(sqlite_session, name="Legacy", user_id=None)
    vacancy = await _vacancy(sqlite_session, "1")
    repo = SavedSearchMatchRepository(sqlite_session)
    await repo.record(own_search.id, vacancy.id)
    await repo.record(other_search.id, vacancy.id)
    await repo.record(legacy.id, vacancy.id)

    assert await repo.count_unseen_for_user(owner.id) == 1
    assert await repo.count_unseen_for_user(other.id) == 1


async def test_one_vacancy_in_two_searches_counts_twice(
    sqlite_session: AsyncSession,
) -> None:
    user = await _user(sqlite_session, "hh-1")
    first = await _search(sqlite_session, name="First", user_id=user.id)
    second = await _search(sqlite_session, name="Second", user_id=user.id)
    vacancy = await _vacancy(sqlite_session, "1")
    repo = SavedSearchMatchRepository(sqlite_session)
    await repo.record(first.id, vacancy.id)
    await repo.record(second.id, vacancy.id)

    assert await repo.count_unseen_for_user(user.id) == 2


async def test_user_methods_return_zero_without_matches(
    sqlite_session: AsyncSession,
) -> None:
    user = await _user(sqlite_session, "hh-1")
    repo = SavedSearchMatchRepository(sqlite_session)

    assert await repo.count_unseen_for_user(user.id) == 0
    assert await repo.mark_seen_for_user(user.id) == 0


async def test_mark_seen_updates_only_unseen_rows_of_owner(
    sqlite_session: AsyncSession,
) -> None:
    owner = await _user(sqlite_session, "hh-1")
    other = await _user(sqlite_session, "hh-2")
    own_search = await _search(sqlite_session, name="Own", user_id=owner.id)
    other_search = await _search(sqlite_session, name="Other", user_id=other.id)
    first = await _vacancy(sqlite_session, "1")
    second = await _vacancy(sqlite_session, "2")
    repo = SavedSearchMatchRepository(sqlite_session)
    await repo.record(own_search.id, first.id)
    await repo.record(own_search.id, second.id)
    await repo.record(other_search.id, first.id)

    already_seen = await sqlite_session.scalar(
        select(SavedSearchMatch).where(
            SavedSearchMatch.saved_search_id == own_search.id,
            SavedSearchMatch.vacancy_id == first.id,
        )
    )
    assert already_seen is not None
    already_seen.seen_at = SEEN_AT
    await sqlite_session.flush()

    assert await repo.mark_seen_for_user(owner.id) == 1
    assert await repo.mark_seen_for_user(owner.id) == 0
    assert await repo.count_unseen_for_user(owner.id) == 0
    assert await repo.count_unseen_for_user(other.id) == 1

    await sqlite_session.refresh(already_seen)
    assert already_seen.seen_at.replace(tzinfo=UTC) == SEEN_AT


async def test_missing_user_returns_zero(sqlite_session: AsyncSession) -> None:
    repo = SavedSearchMatchRepository(sqlite_session)

    assert await repo.count_unseen_for_user(1) == 0
    assert await repo.mark_seen_for_user(1) == 0
