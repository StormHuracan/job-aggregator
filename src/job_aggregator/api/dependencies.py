from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.user import UserRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHOAuthClient
from job_aggregator.services.auth_sessions import AuthSessionService
from job_aggregator.services.tokens import TokenService

SESSION_COOKIE_NAME = "job_aggregator_session"
SESSION_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def get_token_service(session: AsyncSession = Depends(get_db_session)) -> TokenService:
    return TokenService(session)


def get_auth_session_service(
    session: AsyncSession = Depends(get_db_session),
) -> AuthSessionService:
    return AuthSessionService(session)


def get_hh_oauth_client(settings: Settings = Depends(get_settings)) -> HHOAuthClient:
    if not settings.hh_client_id or not settings.hh_client_secret:
        raise HTTPException(status_code=503, detail="Авторизация временно недоступна")
    client = HHOAuthClient(
        client_id=settings.hh_client_id,
        client_secret=settings.hh_client_secret,
    )
    return client


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def _set_session_cookie(response: Response, token: str, *, secure: bool) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=secure,
    )


async def get_current_user(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Владелец действующей серверной сессии или 401 с безопасным сообщением.

    Сессия читается из cookie `job_aggregator_session` и проверяется через
    AuthSessionService. Rolling-продление из JA-63 коммитится здесь только
    при выдаче replacement_token; при ошибке сохранения новая cookie не
    выставляется, а исходная сессия остаётся работоспособной (rollback
    отменяет revoke).
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _unauthorized()

    auth = await AuthSessionService(session).authenticate_session(token)
    if auth is None:
        raise _unauthorized()

    user = await UserRepository(session).get_by_id(auth.user_id)
    if user is None:
        raise _unauthorized()

    if auth.replacement_token is not None:
        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            # rollback() expiry'ит уже загруженные объекты, включая user;
            # перечитываем, чтобы вернуть работоспособный экземпляр.
            user = await UserRepository(session).get_by_id(auth.user_id)
            if user is None:
                raise _unauthorized()
        else:
            _set_session_cookie(
                response,
                auth.replacement_token,
                secure=request.url.scheme == "https",
            )

    return user
