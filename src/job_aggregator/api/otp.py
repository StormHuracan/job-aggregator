import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import _set_session_cookie
from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHAPIClient
from job_aggregator.integrations.hh.errors import (
    HHIntegrationError,
    HHRateLimitError,
    HHTemporaryError,
)
from job_aggregator.integrations.hh.otp import OTPInvalidCode, OTPPrompt
from job_aggregator.services.auth_sessions import AuthSessionService
from job_aggregator.services.otp_login import (
    OTP_COOLDOWN,
    OTP_TTL,
    OTPExpired,
    OTPLoginService,
    OTPThrottled,
    normalize_login,
)

router = APIRouter(prefix="/auth/hh", tags=["auth"])
_COOKIE = "hh_otp_login"


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OTPStart(_Payload):
    username: SecretStr


class OTPVerify(_Payload):
    code: SecretStr


class OTPCaptcha(_Payload):
    text: SecretStr


def _service(request: Request) -> OTPLoginService:
    return request.app.state.otp_logins


def _prompt(prompt: OTPPrompt) -> dict:
    return {
        "step": prompt.step,
        "captcha_image": prompt.captcha_image,
        "retry_after": OTP_COOLDOWN,
        "expires_in": OTP_TTL,
    }


def _error(error: Exception) -> HTTPException:
    if isinstance(error, OTPExpired):
        return HTTPException(410, {"code": "otp_expired"})
    if isinstance(error, OTPThrottled):
        return HTTPException(
            429,
            {"code": "otp_throttled"},
            headers={"Retry-After": str(error.retry_after)},
        )
    if isinstance(error, OTPInvalidCode):
        return HTTPException(400, {"code": "otp_invalid_code"})
    if isinstance(error, HHRateLimitError):
        return HTTPException(
            429, {"code": "otp_throttled"}, headers={"Retry-After": "60"}
        )
    if isinstance(error, HHTemporaryError):
        return HTTPException(503, {"code": "otp_unavailable"})
    return HTTPException(502, {"code": "otp_rejected"})


def _cookie(response: Response, settings: Settings, token: str) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        _COOKIE,
        token,
        max_age=OTP_TTL,
        httponly=True,
        secure=settings.app_env != "local",
        samesite="strict",
        path="/",
    )


@router.get("/options")
async def login_options(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"method": "oauth" if settings.hh_redirect_uri else "otp"}


@router.post("/otp/start")
async def start_otp(
    data: OTPStart,
    request: Request,
    response: Response,
    service: OTPLoginService = Depends(_service),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        username = normalize_login(data.username.get_secret_value())
    except ValueError:
        raise HTTPException(422, {"code": "otp_invalid_login"}) from None
    try:
        # Сначала новая попытка: cooldown не должен уничтожать уже высланный код.
        token, prompt = await service.start(
            username, request.client.host if request.client else "unknown"
        )
        await service.cancel(request.cookies.get(_COOKIE))
    except (OTPThrottled, HHIntegrationError) as error:
        raise _error(error) from None
    _cookie(response, settings, token)
    return _prompt(prompt)


@router.post("/otp/verify")
async def verify_otp(
    data: OTPVerify,
    request: Request,
    response: Response,
    service: OTPLoginService = Depends(_service),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    code = data.code.get_secret_value().strip()
    if not re.fullmatch(r"[0-9]{4,8}", code):
        raise HTTPException(422, {"code": "otp_invalid_code"})
    try:
        result = await service.confirm(request.cookies.get(_COOKIE), code)
        if isinstance(result, OTPPrompt):
            return _prompt(result)
        client = HHAPIClient(result, allow_token_refresh=False)
        try:
            profile = await client.get_current_user()
        finally:
            client.close()
        user = await UserRepository(db).get_or_create(
            profile.hh_user_id, profile.display_name
        )
        await HHAccountRepository(db).save(user.id, result)
        token = await AuthSessionService(db).create_session(user.id)
        await db.commit()
    except (OTPExpired, OTPThrottled, HHIntegrationError) as error:
        await db.rollback()
        raise _error(error) from None
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, {"code": "otp_save_failed"}) from None
    _set_session_cookie(response, token, secure=settings.app_env != "local")
    response.delete_cookie(
        _COOKIE,
        path="/",
        httponly=True,
        secure=settings.app_env != "local",
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"step": "authenticated"}


@router.post("/otp/captcha")
async def solve_captcha(
    data: OTPCaptcha,
    request: Request,
    response: Response,
    service: OTPLoginService = Depends(_service),
) -> dict:
    text = data.text.get_secret_value().strip()
    if not text or len(text) > 100:
        raise HTTPException(422, {"code": "otp_invalid_captcha"})
    try:
        result = await service.captcha(request.cookies.get(_COOKIE), text)
    except (OTPExpired, OTPThrottled, HHIntegrationError) as error:
        raise _error(error) from None
    response.headers["Cache-Control"] = "no-store"
    return _prompt(result)


@router.post("/otp/cancel", status_code=204)
async def cancel_otp(
    request: Request,
    settings: Settings = Depends(get_settings),
    service: OTPLoginService = Depends(_service),
) -> Response:
    await service.cancel(request.cookies.get(_COOKIE))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        _COOKIE,
        path="/",
        httponly=True,
        secure=settings.app_env != "local",
        samesite="strict",
    )
    return response
