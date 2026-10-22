import logging
from secrets import compare_digest
from typing import Annotated
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import (
    _set_session_cookie,
    get_auth_session_service,
    get_current_user,
    get_hh_oauth_client,
)
from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHAPIClient, HHOAuthClient
from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHIntegrationError,
    HHTemporaryError,
)
from job_aggregator.schemas.hh_auth import HHAuthStatusResponse
from job_aggregator.services.auth_sessions import AuthSessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/hh", tags=["auth"])


@router.get("/status", response_model=HHAuthStatusResponse)
async def hh_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> HHAuthStatusResponse:
    tokens = await HHAccountRepository(db).get_by_user_id(user.id)
    if tokens is None:
        return HHAuthStatusResponse(connected=False, access_expires_at=None)
    return HHAuthStatusResponse(
        connected=True,
        access_expires_at=tokens.access_expires_at,
    )


@router.get("/login")
async def hh_login(
    settings: Settings = Depends(get_settings),
    client: HHOAuthClient = Depends(get_hh_oauth_client),
    session: AuthSessionService = Depends(get_auth_session_service),
    async_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    raw_state = await session.create_oauth_state()
    authorization_url = client.get_authorization_url(
        redirect_uri=settings.hh_redirect_uri or "",
        state=raw_state,
    )
    await async_session.commit()
    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/callback")
async def hh_oauth_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    settings: Settings = Depends(get_settings),
    db_session: AsyncSession = Depends(get_db_session),
    oauth_client: HHOAuthClient = Depends(get_hh_oauth_client),
    auth_service: AuthSessionService = Depends(get_auth_session_service),
) -> RedirectResponse:
    """Потребить state и атомарно сохранить персональное подключение и сессию."""
    if not code.strip() or not state.strip():
        raise HTTPException(400, "Некорректные параметры авторизации")
    try:
        valid = await auth_service.consume_oauth_state(state)
        # Code одноразовый: state остаётся потреблённым и при последующем сбое HH.
        await db_session.commit()
    except SQLAlchemyError:
        await db_session.rollback()
        logger.warning("Не удалось сохранить OAuth state")
        raise HTTPException(
            500, "Не удалось завершить вход. Начните авторизацию заново"
        ) from None
    if not valid:
        raise HTTPException(
            400, "Ссылка авторизации недействительна или уже использована"
        )
    try:
        tokens = await oauth_client.exchange_code(code, settings.hh_redirect_uri or "")
        client = HHAPIClient(tokens, allow_token_refresh=False)
        try:
            profile = await client.get_current_user()
        finally:
            client.close()
    except HHIntegrationError as error:
        logger.warning("Не удалось завершить авторизацию HH.ru")
        if isinstance(error, HHTemporaryError):
            code_status = 503
        elif isinstance(error, HHAuthenticationError):
            code_status = 400
        else:
            code_status = 502
        raise HTTPException(
            code_status, "Не удалось войти через HH.ru. Начните авторизацию заново"
        ) from None
    try:
        user = await UserRepository(db_session).get_or_create(
            profile.hh_user_id, profile.display_name
        )
        await HHAccountRepository(db_session).save(user.id, tokens)
        session_token = await auth_service.create_session(user.id)
        await db_session.commit()
    except SQLAlchemyError:
        await db_session.rollback()
        logger.warning("Не удалось сохранить вход пользователя")
        raise HTTPException(
            500, "Не удалось сохранить вход. Начните авторизацию заново"
        ) from None
    response = RedirectResponse("/account", status_code=303)
    _set_session_cookie(response, session_token, secure=settings.app_env != "local")
    return response


_OAUTH_COOKIE = "hh_oauth_state"


class OAuthCompletion(BaseModel):
    """Адрес мобильного возврата передаётся только в теле POST, без логирования."""

    model_config = ConfigDict(extra="forbid")
    return_url: SecretStr


@router.post("/start")
async def start_browser_login(
    response: Response,
    settings: Settings = Depends(get_settings),
    client: HHOAuthClient = Depends(get_hh_oauth_client),
    session: AuthSessionService = Depends(get_auth_session_service),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Начать браузерный вход с привязкой одноразового state к браузеру."""
    try:
        state = await session.create_oauth_state()
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Не удалось начать вход. Попробуйте ещё раз") from None
    response.set_cookie(
        _OAUTH_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.app_env != "local",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "mode": "redirect" if settings.hh_redirect_uri else "mobile",
        "authorization_url": client.get_authorization_url(
            settings.hh_redirect_uri or "", state
        ),
    }


@router.post("/complete", status_code=204)
async def complete_browser_login(
    data: OAuthCompletion,
    request: Request,
    settings: Settings = Depends(get_settings),
    oauth_client: HHOAuthClient = Depends(get_hh_oauth_client),
    auth_service: AuthSessionService = Depends(get_auth_session_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Завершить мобильный OAuth без передачи code в URL нашего сайта."""
    invalid = HTTPException(400, "Адрес возврата недействителен. Начните вход заново")
    try:
        raw = data.return_url.get_secret_value().strip()
        if len(raw) > 8192:
            raise invalid
        url = urlsplit(raw)
        query = parse_qs(url.query, max_num_fields=10)
        (code,) = query.get("code", [])
        (state,) = query.get("state", [])
        cookie = request.cookies.get(_OAUTH_COOKIE, "")
        if (
            url.scheme != "hhandroid"
            or url.netloc != "oauthresponse"
            or url.path not in ("", "/")
            or url.fragment
            or not cookie
            or not compare_digest(state.encode(), cookie.encode())
        ):
            raise invalid
    except ValueError, TypeError:
        raise invalid from None
    result = await hh_oauth_callback(
        code=code,
        state=state,
        settings=settings,
        oauth_client=oauth_client,
        auth_service=auth_service,
        db_session=db_session,
    )
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    # Сохраняем HttpOnly session-cookie, созданную общим callback.
    for key, value in result.raw_headers:
        if key == b"set-cookie":
            response.raw_headers.append((key, value))
    response.delete_cookie(
        _OAUTH_COOKIE,
        path="/",
        httponly=True,
        secure=settings.app_env != "local",
        samesite="lax",
    )
    return response
