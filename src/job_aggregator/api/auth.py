import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
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
