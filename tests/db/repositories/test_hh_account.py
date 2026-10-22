from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from tests.factories import make_token_data


async def test_missing_account(sqlite_session: AsyncSession) -> None:
    assert await HHAccountRepository(sqlite_session).get_by_user_id(42) is None


async def test_save_and_update_are_scoped_to_user(sqlite_session: AsyncSession) -> None:
    first = User(hh_user_id="first", display_name="Первый")
    second = User(hh_user_id="second", display_name="Второй")
    sqlite_session.add_all([first, second])
    await sqlite_session.flush()
    repo = HHAccountRepository(sqlite_session)
    tokens = make_token_data()
    assert await repo.save(first.id, tokens) is True
    assert await repo.save(second.id, tokens) is True
    assert await repo.save(first.id, tokens) is False
    updated = make_token_data(access_token="new-access", refresh_token="new-refresh")
    assert await repo.save(first.id, updated) is True
    account = await repo.get_by_user_id(first.id)
    other = await repo.get_by_user_id(second.id)
    assert account is not None and other is not None
    assert account.id != other.id
    assert account.access_token == "new-access"
    assert account.refresh_token == "new-refresh"
    assert other.access_token == tokens.access_token
    assert account.created_at is not None and account.updated_at is not None
    assert "new-access" not in repr(account)
    assert "new-refresh" not in repr(account)


@pytest.mark.parametrize(
    "field", ["access_token", "refresh_token", "access_expires_at"]
)
async def test_each_token_field_triggers_update(
    sqlite_session: AsyncSession, field: str
) -> None:
    user = User(hh_user_id="42", display_name="Пользователь")
    sqlite_session.add(user)
    await sqlite_session.flush()
    repo = HHAccountRepository(sqlite_session)
    tokens = make_token_data()
    await repo.save(user.id, tokens)
    change = (
        tokens.access_expires_at + timedelta(hours=1)
        if field == "access_expires_at"
        else "changed"
    )
    updated = make_token_data(**{field: change})
    assert await repo.save(user.id, updated) is True
    current = await repo.get_by_user_id(user.id)
    assert current is not None
    assert getattr(current, field) == change
    assert await repo.save(user.id, updated) is False


async def test_save_does_not_commit(sqlite_session: AsyncSession) -> None:
    user = User(hh_user_id="42", display_name="Пользователь")
    sqlite_session.add(user)
    await sqlite_session.commit()
    user_id = user.id
    repo = HHAccountRepository(sqlite_session)
    await repo.save(user_id, make_token_data())
    await sqlite_session.rollback()
    assert await repo.get_by_user_id(user_id) is None


async def test_unknown_user_does_not_break_transaction(
    sqlite_session: AsyncSession,
) -> None:
    repo = HHAccountRepository(sqlite_session)
    with pytest.raises(ValueError, match="Пользователь не найден"):
        await repo.save(42, make_token_data())
    assert sqlite_session.is_active


def test_expiry_normalized_and_naive_rejected() -> None:
    account = HHAccount(
        user_id=1,
        access_token="secret-access",
        refresh_token="secret-refresh",
        access_expires_at=datetime(
            2026, 10, 19, 15, tzinfo=timezone(timedelta(hours=3))
        ),
    )
    assert account.access_expires_at == datetime(2026, 10, 19, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        account.access_expires_at = datetime(2026, 10, 19)
