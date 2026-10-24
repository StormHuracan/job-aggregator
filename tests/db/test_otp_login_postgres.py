from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.otp import _service
from job_aggregator.db.models.auth_session import UserSession
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User, UserSettings
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.dto import HHUserProfile
from job_aggregator.services.auth_sessions import AuthSessionService
from tests.factories import make_token_data


@pytest.mark.parametrize("commit_fails", [False, True])
async def test_otp_login_is_atomic_on_postgres(
    app, async_client, pg_session_factory, monkeypatch, commit_fails
):
    async def database():
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = database
    service = AsyncMock()
    service.confirm.return_value = make_token_data()
    app.dependency_overrides[_service] = lambda: service
    monkeypatch.setattr(
        "job_aggregator.api.otp.HHAPIClient.get_current_user",
        AsyncMock(return_value=HHUserProfile("hh-otp", "Пользователь")),
    )
    if commit_fails:
        monkeypatch.setattr(
            AsyncSession, "commit", AsyncMock(side_effect=SQLAlchemyError("secret"))
        )
    response = await async_client.post("/auth/hh/otp/verify", json={"code": "1234"})
    assert response.status_code == (500 if commit_fails else 200)
    assert "secret" not in response.text
    async with pg_session_factory() as check:
        for model in (User, UserSettings, HHAccount, UserSession):
            assert await check.scalar(select(func.count()).select_from(model)) == (
                0 if commit_fails else 1
            )
        if commit_fails:
            assert "set-cookie" not in response.headers
        else:
            token = response.cookies.get("job_aggregator_session")
            assert token is not None
            assert await AuthSessionService(check).get_user_id(token) is not None
