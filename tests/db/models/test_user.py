import pytest
from sqlalchemy import Integer, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.base import Base, TimestampMixin
from job_aggregator.db.models.user import User, UserSettings


def test_user_and_settings_inherit_shared_orm_base() -> None:
    assert issubclass(User, Base)
    assert issubclass(UserSettings, Base)
    assert issubclass(User, TimestampMixin)
    assert issubclass(UserSettings, TimestampMixin)


def test_user_uses_hh_identity_and_settings_use_user_as_primary_key() -> None:
    assert set(User.__table__.columns.keys()) == {
        "id",
        "hh_user_id",
        "display_name",
        "created_at",
        "updated_at",
    }
    assert set(UserSettings.__table__.columns.keys()) == {
        "user_id",
        "default_area",
        "default_pages_limit",
        "created_at",
        "updated_at",
    }
    assert User.__table__.columns["hh_user_id"].unique is True
    assert UserSettings.__table__.columns["user_id"].primary_key is True
    assert UserSettings.__table__.columns["user_id"].foreign_keys
    assert isinstance(
        UserSettings.__table__.columns["default_pages_limit"].type, Integer
    )


async def test_user_settings_has_server_default_pages_limit(
    sqlite_session: AsyncSession,
) -> None:
    user = User(hh_user_id="hh-42", display_name="Daniil")
    sqlite_session.add(user)
    await sqlite_session.flush()

    await sqlite_session.execute(insert(UserSettings).values(user_id=user.id))
    await sqlite_session.commit()

    settings = await sqlite_session.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )

    assert settings is not None
    assert settings.default_area is None
    assert settings.default_pages_limit == 5


async def test_user_hh_identity_is_unique(sqlite_session: AsyncSession) -> None:
    sqlite_session.add_all(
        [
            User(hh_user_id="hh-42", display_name="Daniil"),
            User(hh_user_id="hh-42", display_name="Another Daniil"),
        ]
    )

    with pytest.raises(IntegrityError):
        await sqlite_session.commit()
