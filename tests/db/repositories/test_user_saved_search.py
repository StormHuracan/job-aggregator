import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.saved_search import (
    UserSavedSearchRepository,
)


async def _create_user(session: AsyncSession, hh_id: str) -> User:
    user = User(hh_user_id=hh_id, display_name=hh_id)
    session.add(user)
    await session.commit()
    return user


async def _create_search(
    repo: UserSavedSearchRepository,
    user_id: int,
    name: str,
    text: str = "text",
) -> SavedSearch:
    return await repo.create(
        user_id,
        name=name,
        text=text,
        area=None,
        min_salary=None,
        max_salary=None,
    )


@pytest.fixture
async def users(sqlite_session: AsyncSession) -> tuple[User, User]:
    alice = await _create_user(sqlite_session, "hh-alice")
    bob = await _create_user(sqlite_session, "hh-bob")
    return alice, bob


async def test_create_saves_owner_criteria_and_is_enabled(
    sqlite_session: AsyncSession, users: tuple[User, User]
) -> None:
    alice, _ = users
    repo = UserSavedSearchRepository(sqlite_session)

    search = await repo.create(
        alice.id,
        name="Python",
        text="python",
        area="1",
        min_salary=100_000,
        max_salary=200_000,
    )
    await sqlite_session.commit()

    assert search.id is not None
    assert search.user_id == alice.id
    assert search.name == "Python"
    assert search.text == "python"
    assert search.area == "1"
    assert search.min_salary == 100_000
    assert search.max_salary == 200_000
    assert search.is_enabled is True


async def test_list_for_user_isolates_owners_and_sorts(
    sqlite_session: AsyncSession, users: tuple[User, User]
) -> None:
    alice, bob = users
    repo = UserSavedSearchRepository(sqlite_session)

    s1 = await _create_search(repo, alice.id, "A1")
    s2 = await _create_search(repo, alice.id, "A2")
    await _create_search(repo, bob.id, "B1")

    # Запись без владельца
    sqlite_session.add(SavedSearch(name="Orphan", text="x"))
    await sqlite_session.commit()

    alice_items = await repo.list_for_user(alice.id)
    bob_items = await repo.list_for_user(bob.id)

    assert [s.id for s in alice_items] == [s1.id, s2.id]
    assert [s.name for s in alice_items] == ["A1", "A2"]
    assert [s.name for s in bob_items] == ["B1"]
    assert all(s.name != "Orphan" for s in alice_items + bob_items)


async def test_get_for_user_hides_foreign_and_orphan(
    sqlite_session: AsyncSession, users: tuple[User, User]
) -> None:
    alice, bob = users
    repo = UserSavedSearchRepository(sqlite_session)

    alice_search = await _create_search(repo, alice.id, "A")

    orphan = SavedSearch(name="Orphan", text="x")
    sqlite_session.add(orphan)
    await sqlite_session.commit()

    assert await repo.get_for_user(alice.id, alice_search.id) is not None
    assert await repo.get_for_user(bob.id, alice_search.id) is None
    assert await repo.get_for_user(alice.id, orphan.id) is None
    assert await repo.get_for_user(alice.id, 999_999) is None


async def test_set_enabled_isolates_foreign_and_toggles_own(
    sqlite_session: AsyncSession, users: tuple[User, User]
) -> None:
    alice, bob = users
    repo = UserSavedSearchRepository(sqlite_session)

    search = await _create_search(repo, alice.id, "A")
    await sqlite_session.commit()

    assert await repo.set_enabled(bob.id, search.id, False) is None
    assert await repo.set_enabled(alice.id, 999_999, False) is None

    updated = await repo.set_enabled(alice.id, search.id, False)
    assert updated is not None
    assert updated.is_enabled is False


async def test_list_enabled_for_user_excludes_disabled(
    sqlite_session: AsyncSession, users: tuple[User, User]
) -> None:
    alice, _ = users
    repo = UserSavedSearchRepository(sqlite_session)

    s1 = await _create_search(repo, alice.id, "A1")
    s2 = await _create_search(repo, alice.id, "A2")
    await repo.set_enabled(alice.id, s1.id, False)
    await sqlite_session.commit()

    result = await repo.list_enabled_for_user(alice.id)
    assert [s.id for s in result] == [s2.id]


async def test_repository_does_not_commit(
    sqlite_session: AsyncSession, users: tuple[User, User]
) -> None:
    alice, _ = users
    repo = UserSavedSearchRepository(sqlite_session)

    await _create_search(repo, alice.id, "A")
    await sqlite_session.rollback()

    count = await sqlite_session.scalar(
        select(func.count())
        .select_from(SavedSearch)
        .where(SavedSearch.user_id == alice.id)
    )
    assert count == 0
