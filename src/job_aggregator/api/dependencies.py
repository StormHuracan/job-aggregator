from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHOAuthClient
from job_aggregator.services.auth_sessions import AuthSessionService
from job_aggregator.services.tokens import TokenService


def get_token_service(session: AsyncSession = Depends(get_db_session)) -> TokenService:
    return TokenService(session)


def get_auth_session_service(
        session: AsyncSession = Depends(get_db_session),
) -> AuthSessionService:
    return AuthSessionService(session)


def get_hh_oauth_client(settings: Settings = Depends(get_settings)) -> HHOAuthClient:
    if not settings.hh_client_id or  not settings.hh_client_secret:
        raise HTTPException(status_code=503, detail="Авторизация временно недоступна")
    client = HHOAuthClient(
        client_id=settings.hh_client_id,
        client_secret=settings.hh_client_secret
    )
    return client
