from datetime import UTC, datetime

import pytest

from job_aggregator.api.dependencies import SESSION_COOKIE_NAME
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.services.auth_sessions import AuthSessionService
from tests.factories import make_token_data


@pytest.fixture
async def status_db(app, sqlite_session):
    async def db():
        yield sqlite_session

    app.dependency_overrides[get_db_session] = db
    return sqlite_session


async def test_status_requires_session(async_client, status_db):
    assert (await async_client.get("/auth/hh/status")).status_code == 401


@pytest.mark.parametrize(
    "expiry", [None, datetime(2100, 1, 1, tzinfo=UTC), datetime(2000, 1, 1, tzinfo=UTC)]
)
async def test_status_reads_only_current_owner(async_client, status_db, expiry):
    user = await UserRepository(status_db).get_or_create("current", "Current")
    other = await UserRepository(status_db).get_or_create("other", "Other")
    await HHAccountRepository(status_db).save(other.id, make_token_data())
    if expiry:
        await HHAccountRepository(status_db).save(
            user.id, make_token_data(access_expires_at=expiry)
        )
    token = await AuthSessionService(status_db).create_session(user.id)
    await status_db.commit()
    async_client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await async_client.get("/auth/hh/status")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"connected", "access_expires_at"}
    assert data["connected"] == (expiry is not None)
    assert (
        datetime.fromisoformat(data["access_expires_at"])
        if expiry
        else data["access_expires_at"]
    ) == expiry
