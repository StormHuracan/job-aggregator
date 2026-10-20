import pytest
from sqlalchemy import Boolean, DateTime, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.base import Base, TimestampMixin
from job_aggregator.db.models.saved_search import SavedSearch


def test_saved_search_table_name() -> None:
    assert SavedSearch.__tablename__ == "saved_searches"
    assert SavedSearch.__table__.name == "saved_searches"


def test_saved_search_inherits_base_and_timestamp_mixin() -> None:
    assert issubclass(SavedSearch, Base)
    assert issubclass(SavedSearch, TimestampMixin)


def test_saved_search_model_structure() -> None:
    expected_fields = {
        "id",
        "name",
        "text",
        "area",
        "is_enabled",
        "created_at",
        "updated_at",
        "user_id",
        "min_salary",
        "max_salary",
    }

    actual_fields = set(SavedSearch.__table__.columns.keys())

    assert actual_fields == expected_fields


def test_saved_search_id_is_primary_key() -> None:
    assert SavedSearch.__table__.columns["id"].primary_key


@pytest.mark.parametrize(
    "column_name",
    ["id", "name", "text", "is_enabled", "created_at", "updated_at"],
)
def test_saved_search_required_columns(column_name: str) -> None:
    assert SavedSearch.__table__.columns[column_name].nullable is False


def test_saved_search_area_is_optional() -> None:
    assert SavedSearch.__table__.columns["area"].nullable is True


def test_saved_search_is_enabled_column_config() -> None:
    column = SavedSearch.__table__.columns["is_enabled"]

    assert isinstance(column.type, Boolean)
    assert column.default.arg is True
    assert column.server_default is not None


@pytest.mark.parametrize("column_name", ["created_at", "updated_at"])
def test_saved_search_timestamp_columns_are_timezone_aware(column_name: str) -> None:
    column_type = SavedSearch.__table__.columns[column_name].type

    assert isinstance(column_type, DateTime)
    assert column_type.timezone is True


def test_saved_search_strips_text() -> None:
    search = SavedSearch(name="Python", text="  python developer  ")

    assert search.text == "python developer"


@pytest.mark.parametrize("text", ["", " ", "   ", "\t\n "])
def test_saved_search_rejects_blank_text(text: str) -> None:
    with pytest.raises(ValueError):
        SavedSearch(name="Python", text=text)


async def test_saved_search_db_rejects_blank_text(sqlite_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await sqlite_session.execute(
            insert(SavedSearch).values(name="Python", text="   ")
        )


async def test_saved_search_can_be_saved(sqlite_session: AsyncSession) -> None:
    search = SavedSearch(name="Python Москва", text="python", area="1")

    sqlite_session.add(search)
    await sqlite_session.commit()
    await sqlite_session.refresh(search)

    assert search.id is not None
    assert search.name == "Python Москва"
    assert search.text == "python"
    assert search.area == "1"


async def test_saved_search_area_can_be_none(sqlite_session: AsyncSession) -> None:
    search = SavedSearch(name="Python", text="python")

    sqlite_session.add(search)
    await sqlite_session.commit()
    await sqlite_session.refresh(search)

    assert search.area is None


async def test_saved_search_is_enabled_by_default(sqlite_session: AsyncSession) -> None:
    search = SavedSearch(name="Python", text="python")

    sqlite_session.add(search)
    await sqlite_session.commit()
    await sqlite_session.refresh(search)

    assert search.is_enabled is True


async def test_saved_search_server_default_is_enabled(
    sqlite_session: AsyncSession,
) -> None:
    await sqlite_session.execute(
        insert(SavedSearch).values(name="Python", text="python")
    )
    await sqlite_session.commit()

    is_enabled = await sqlite_session.scalar(select(SavedSearch.is_enabled))

    assert is_enabled is True


async def test_saved_search_can_be_disabled(sqlite_session: AsyncSession) -> None:
    search = SavedSearch(name="Python", text="python", is_enabled=False)

    sqlite_session.add(search)
    await sqlite_session.commit()
    await sqlite_session.refresh(search)

    assert search.is_enabled is False


async def test_saved_search_timestamps_filled_on_insert(
    sqlite_session: AsyncSession,
) -> None:
    search = SavedSearch(name="Python", text="python")

    sqlite_session.add(search)
    await sqlite_session.commit()
    await sqlite_session.refresh(search)

    assert search.created_at is not None
    assert search.updated_at is not None


@pytest.mark.parametrize("missing_field", ["name", "text"])
async def test_saved_search_required_fields_enforced(
    sqlite_session: AsyncSession, missing_field: str
) -> None:
    fields = {"name": "Python", "text": "python"}
    del fields[missing_field]

    sqlite_session.add(SavedSearch(**fields))

    with pytest.raises(IntegrityError):
        await sqlite_session.commit()


async def test_saved_search_is_enabled_cannot_be_null(
    sqlite_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await sqlite_session.execute(
            insert(SavedSearch).values(name="Python", text="python", is_enabled=None)
        )
