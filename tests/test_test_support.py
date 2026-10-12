from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.hh_account_token import HHAccountToken
from tests.factories import make_token_data, make_vacancy_data


def test_vacancy_factory_returns_independent_data() -> None:
    first = make_vacancy_data(raw_data={"id": "123"})
    second = make_vacancy_data()

    first.title = "Changed"
    first.raw_data["id"] = "changed"

    assert second.title == "Python developer"
    assert second.raw_data is None
    assert first is not second


def test_token_factory_accepts_explicit_expiry() -> None:
    expiry = datetime(2030, 1, 1, tzinfo=UTC)
    tokens = make_token_data(access_token="custom", access_expires_at=expiry)

    assert tokens.access_token == "custom"
    assert tokens.access_expires_at == expiry


@pytest.mark.parametrize("access_token", ["first", "second"])
async def test_sqlite_session_starts_empty(
    sqlite_session: AsyncSession, access_token: str
) -> None:
    count = await sqlite_session.scalar(
        select(func.count()).select_from(HHAccountToken)
    )
    assert count == 0

    tokens = make_token_data(access_token=access_token)
    sqlite_session.add(HHAccountToken(**tokens.model_dump()))
    await sqlite_session.commit()
