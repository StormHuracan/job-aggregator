from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import DateTime
from sqlalchemy.exc import IntegrityError

from job_aggregator.db.base import Base, TimestampMixin
from job_aggregator.db.models.hh_account_token import HHAccountToken
from job_aggregator.db.session import create_engine_and_factory

EXPIRES_AT = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session():
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


def test_hh_account_token_table_name() -> None:
    assert HHAccountToken.__tablename__ == "hh_account_tokens"
    assert HHAccountToken.__table__.name == "hh_account_tokens"


def test_hh_account_token_inherits_base_and_timestamp_mixin() -> None:
    assert issubclass(HHAccountToken, Base)
    assert issubclass(HHAccountToken, TimestampMixin)


def test_hh_account_token_model_structure() -> None:
    expected_fields = {
        "id",
        "singleton",
        "access_token",
        "refresh_token",
        "access_expires_at",
        "created_at",
        "updated_at",
    }

    actual_fields = set(HHAccountToken.__table__.columns.keys())

    assert actual_fields == expected_fields


def test_hh_account_token_id_is_primary_key() -> None:
    columns = HHAccountToken.__table__.columns

    assert columns["id"].primary_key


@pytest.mark.parametrize(
    "column_name",
    [
        "id",
        "access_token",
        "refresh_token",
        "access_expires_at",
        "created_at",
        "updated_at",
    ],
)
def test_hh_account_token_required_columns(column_name: str) -> None:
    column = HHAccountToken.__table__.columns[column_name]

    assert column.nullable is False


@pytest.mark.parametrize(
    "column_name", ["access_expires_at", "created_at", "updated_at"]
)
def test_hh_account_token_datetime_columns_are_timezone_aware(
    column_name: str,
) -> None:
    column_type = HHAccountToken.__table__.columns[column_name].type

    assert isinstance(column_type, DateTime)
    assert column_type.timezone is True


def test_access_expires_at_is_normalized_to_utc() -> None:
    moscow = timezone(timedelta(hours=3))
    token = HHAccountToken(
        access_token="access",
        refresh_token="refresh",
        access_expires_at=datetime(2026, 10, 6, 15, 0, tzinfo=moscow),
    )

    assert token.access_expires_at == EXPIRES_AT
    assert token.access_expires_at.utcoffset() == timedelta(0)


def test_access_expires_at_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        HHAccountToken(
            access_token="access",
            refresh_token="refresh",
            access_expires_at=datetime(2026, 10, 6, 12, 0),
        )


def test_hh_account_token_repr_hides_token_values() -> None:
    token = HHAccountToken(
        access_token="secret-access-token",
        refresh_token="secret-refresh-token",
        access_expires_at=EXPIRES_AT,
    )

    text = repr(token)

    assert "secret-access-token" not in text
    assert "secret-refresh-token" not in text


async def test_hh_account_token_can_be_saved(session) -> None:
    token = HHAccountToken(
        access_token="access",
        refresh_token="refresh",
        access_expires_at=EXPIRES_AT,
    )

    session.add(token)
    await session.commit()
    await session.refresh(token)

    assert token.id is not None
    assert token.access_token == "access"
    assert token.refresh_token == "refresh"


async def test_hh_account_token_timestamps_filled_on_insert(session) -> None:
    token = HHAccountToken(
        access_token="access",
        refresh_token="refresh",
        access_expires_at=EXPIRES_AT,
    )

    session.add(token)
    await session.commit()
    await session.refresh(token)

    assert token.created_at is not None
    assert token.updated_at is not None


@pytest.mark.parametrize(
    "missing_field", ["access_token", "refresh_token", "access_expires_at"]
)
async def test_hh_account_token_required_fields_enforced(
    session, missing_field: str
) -> None:
    fields = {
        "access_token": "access",
        "refresh_token": "refresh",
        "access_expires_at": EXPIRES_AT,
    }
    del fields[missing_field]

    session.add(HHAccountToken(**fields))

    with pytest.raises(IntegrityError):
        await session.commit()
