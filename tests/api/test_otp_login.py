from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from job_aggregator.api.otp import _service
from job_aggregator.db.models.auth_session import UserSession
from job_aggregator.db.models.hh_account import HHAccount
from job_aggregator.db.models.user import User
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.dto import HHUserProfile
from job_aggregator.integrations.hh.errors import HHTemporaryError
from job_aggregator.integrations.hh.otp import OTPInvalidCode, OTPPrompt
from job_aggregator.services.auth_sessions import AuthSessionService
from job_aggregator.services.otp_login import OTPExpired, OTPThrottled
from tests.factories import make_token_data


@pytest.fixture
def otp_service(app):
    """Подменяет только сетевой flow; cookie, API и сохранение остаются реальными."""
    service = AsyncMock()
    service.start.return_value = ("opaque-browser-secret", OTPPrompt("code"))
    service.confirm.return_value = make_token_data()
    app.dependency_overrides[_service] = lambda: service
    return service


async def test_start_uses_http_only_cookie_not_json(async_client, otp_service):
    response = await async_client.post(
        "/auth/hh/otp/start", json={"username": " A@example.test "}
    )
    assert response.status_code == 200
    assert response.json()["step"] == "code"
    assert "opaque-browser-secret" not in response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    assert otp_service.start.call_args.args[0] == "a@example.test"


async def test_cooldown_does_not_cancel_existing_code(async_client, otp_service):
    otp_service.start.side_effect = OTPThrottled(33)
    async_client.cookies.set("hh_otp_login", "existing-flow")
    response = await async_client.post(
        "/auth/hh/otp/start", json={"username": "a@example.test"}
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "33"
    otp_service.cancel.assert_not_awaited()


async def test_verify_commits_profile_account_and_session_before_cookie(
    async_client, app, otp_service, sqlite_session, monkeypatch
):
    app.dependency_overrides[get_db_session] = lambda: sqlite_session
    profile = AsyncMock(return_value=HHUserProfile("hh-one", "Имя"))
    monkeypatch.setattr("job_aggregator.api.otp.HHAPIClient.get_current_user", profile)
    async_client.cookies.set("hh_otp_login", "opaque-browser-secret")
    response = await async_client.post("/auth/hh/otp/verify", json={"code": "123456"})
    assert response.status_code == 200
    assert response.json() == {"step": "authenticated"}
    assert "access_token" not in response.text
    token = response.cookies.get("job_aggregator_session")
    assert token
    factory = async_sessionmaker(sqlite_session.bind, expire_on_commit=False)
    async with factory() as check:
        assert await check.scalar(select(func.count()).select_from(HHAccount)) == 1
        assert await check.scalar(select(func.count()).select_from(UserSession)) == 1
        assert await AuthSessionService(check).get_user_id(token) is not None
    assert 'hh_otp_login=""' in response.headers["set-cookie"]


async def test_commit_failure_never_issues_cookie(
    async_client, app, otp_service, sqlite_session, monkeypatch
):
    app.dependency_overrides[get_db_session] = lambda: sqlite_session
    # SQLite legacy mode иначе выпускает первый SAVEPOINT как отдельный commit.
    await sqlite_session.execute(text("BEGIN"))
    monkeypatch.setattr(
        "job_aggregator.api.otp.HHAPIClient.get_current_user",
        AsyncMock(return_value=HHUserProfile("hh-one", "Имя")),
    )
    monkeypatch.setattr(
        sqlite_session, "commit", AsyncMock(side_effect=SQLAlchemyError("private-sql"))
    )
    response = await async_client.post("/auth/hh/otp/verify", json={"code": "1234"})
    assert response.status_code == 500
    assert "set-cookie" not in response.headers
    assert "private-sql" not in response.text
    assert await sqlite_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize(
    "error,status",
    [
        (OTPExpired(), 410),
        (OTPInvalidCode("secret"), 400),
        (HHTemporaryError("secret"), 503),
    ],
)
async def test_verify_safe_error_mapping(
    async_client, app, otp_service, sqlite_session, error, status
):
    app.dependency_overrides[get_db_session] = lambda: sqlite_session
    otp_service.confirm.side_effect = error
    response = await async_client.post("/auth/hh/otp/verify", json={"code": "1234"})
    assert response.status_code == status
    assert "secret" not in response.text
    assert "set-cookie" not in response.headers


async def test_captcha_and_cancel(async_client, otp_service):
    otp_service.captcha.return_value = OTPPrompt("code")
    async_client.cookies.set("hh_otp_login", "flow")
    response = await async_client.post("/auth/hh/otp/captcha", json={"text": "answer"})
    assert response.json()["step"] == "code"
    otp_service.captcha.assert_awaited_once_with("flow", "answer")
    response = await async_client.post("/auth/hh/otp/cancel")
    assert response.status_code == 204
    otp_service.cancel.assert_awaited_once_with("flow")
