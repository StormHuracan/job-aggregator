from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import (
    get_auth_session_service,
    get_hh_oauth_client,
    get_token_service,
)
from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHOAuthClient
from job_aggregator.schemas.hh_auth import HHAuthStatusResponse
from job_aggregator.services.auth_sessions import AuthSessionService
from job_aggregator.services.tokens import TokenService

router = APIRouter(prefix="/auth/hh", tags=["auth"])


@router.get("/status", response_model=HHAuthStatusResponse)
async def hh_status(
    token_service: TokenService = Depends(get_token_service),
) -> HHAuthStatusResponse:
    tokens = await token_service.get_current()
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
    if not settings.hh_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Авторизация временно недоступна",
        )

    raw_state = await session.create_oauth_state()
    authorization_url = client.get_authorization_url(
        redirect_uri=settings.hh_redirect_uri,
        state=raw_state,
    )
    await async_session.commit()
    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
