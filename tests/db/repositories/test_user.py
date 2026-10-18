from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.repositories.user import UserRepository, UserSettingsRepository


async def _count(session: AsyncSession, model: type) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_get_or_create_creates_user_with_default_settings(
    sqlite_session: AsyncSession,
) -> None:
    user = await UserRepository(sqlite_session).get_or_create("42", "Ivan")

    settings = await sqlite_session.get(UserSettings, user.id)
    assert user.hh_user_id == "42"
    assert settings is not None
    assert settings.default_area is None
    assert settings.default_pages_limit == 5


async def test_repeated_get_or_create_returns_same_user(
    sqlite_session: AsyncSession,
) -> None:
    repo = UserRepository(sqlite_session)

    first = await repo.get_or_create("42", "Ivan")
    second = await repo.get_or_create("42", "Ivan")

    assert second.id == first.id
    assert await _count(sqlite_session, User) == 1
    assert await _count(sqlite_session, UserSettings) == 1


async def test_get_by_id_returns_none_for_missing_user(
    sqlite_session: AsyncSession,
) -> None:
    assert await UserRepository(sqlite_session).get_by_id(999) is None


async def test_update_changes_only_passed_fields(sqlite_session: AsyncSession) -> None:
    user = await UserRepository(sqlite_session).get_or_create("42", "Ivan")
    repo = UserSettingsRepository(sqlite_session)
    await repo.update(user.id, default_area="Moscow")

    settings = await repo.update(user.id, default_pages_limit=10)

    assert settings is not None
    assert settings.default_area == "Moscow"
    assert settings.default_pages_limit == 10


async def test_update_with_none_clears_area(sqlite_session: AsyncSession) -> None:
    user = await UserRepository(sqlite_session).get_or_create("42", "Ivan")
    repo = UserSettingsRepository(sqlite_session)
    await repo.update(user.id, default_area="Moscow")

    settings = await repo.update(user.id, default_area=None)

    assert settings is not None
    assert settings.default_area is None


async def test_update_returns_none_for_missing_user(
    sqlite_session: AsyncSession,
) -> None:
    result = await UserSettingsRepository(sqlite_session).update(
        999, default_area="Moscow"
    )

    assert result is None


async def test_repositories_do_not_commit(sqlite_session: AsyncSession) -> None:
    original_commit = sqlite_session.commit
    commit_called = False

    async def track_commit() -> None:
        nonlocal commit_called
        commit_called = True
        await original_commit()

    sqlite_session.commit = track_commit  # type: ignore[method-assign]
    try:
        user = await UserRepository(sqlite_session).get_or_create("42", "Ivan")
        await UserSettingsRepository(sqlite_session).update(user.id, default_area="X")

        assert commit_called is False
    finally:
        sqlite_session.commit = original_commit  # type: ignore[method-assign]
