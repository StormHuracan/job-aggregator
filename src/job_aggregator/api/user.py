import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import SESSION_COOKIE_NAME, get_current_user
from job_aggregator.core.config import get_settings
from job_aggregator.db.models.telegram_binding import TelegramBinding
from job_aggregator.db.models.telegram_link_token import TelegramLinkToken
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.hh_account import HHAccountRepository
from job_aggregator.db.repositories.saved_search_match import SavedSearchMatchRepository
from job_aggregator.db.repositories.user import UserSettingsRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.schemas.telegram import TelegramLinkResponse
from job_aggregator.schemas.user import (
    CurrentUserResponse,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from job_aggregator.services.auth_sessions import AuthSessionService

router = APIRouter(tags=["user"])


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    """Профиль и число непросмотренных совпадений текущего пользователя."""
    try:
        settings = await UserSettingsRepository(db).get_or_create(user.id)
        account = await HHAccountRepository(db).get_by_user_id(user.id)
        result = CurrentUserResponse(
            id=user.id,
            display_name=user.display_name,
            hh_connected=account is not None,
            access_expires_at=account.access_expires_at if account else None,
            new_matches_count=await SavedSearchMatchRepository(
                db
            ).count_unseen_for_user(user.id),
            settings=UserSettingsResponse(
                default_area=settings.default_area,
                default_pages_limit=settings.default_pages_limit,
            ),
        )
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Не удалось загрузить профиль") from None

    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/me/matches/mark-seen", status_code=204)
async def mark_matches_seen(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Сохраняет просмотр непрочитанных совпадений только текущего владельца."""
    try:
        await SavedSearchMatchRepository(db).mark_seen_for_user(user.id)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            500, "Не удалось отметить совпадения просмотренными"
        ) from None
    response.headers["Cache-Control"] = "no-store"


@router.patch("/me/settings", response_model=UserSettingsResponse)
async def update_settings(
    data: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserSettingsResponse:
    """Сохраняет только явно переданные настройки текущего владельца."""
    if (
        "default_pages_limit" in data.model_fields_set
        and data.default_pages_limit is None
    ):
        raise HTTPException(
            422, "Количество страниц должно быть положительным целым числом"
        )

    try:
        settings = await UserSettingsRepository(db).update(
            user.id, **data.model_dump(exclude_unset=True)
        )
        result = UserSettingsResponse(
            default_area=settings.default_area,
            default_pages_limit=settings.default_pages_limit,
        )
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Не удалось сохранить настройки") from None

    return result


@router.post("/me/telegram/link", response_model=TelegramLinkResponse)
async def create_telegram_link(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TelegramLinkResponse:
    """Создаёт одноразовую ссылку для привязки Telegram."""
    settings = get_settings()

    if not settings.telegram_enabled:
        raise HTTPException(503, "Уведомления Telegram отключены")

    if not settings.telegram_bot_token or not settings.telegram_bot_username:
        raise HTTPException(503, "Telegram не настроен")

    try:
        binding = await db.scalar(
            select(TelegramBinding).where(TelegramBinding.user_id == user.id)
        )
        if binding is not None:
            raise HTTPException(
                409,
                "Сначала отключите текущую привязку Telegram",
            )

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=10)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        await db.execute(
            delete(TelegramLinkToken).where(
                TelegramLinkToken.user_id == user.id,
                TelegramLinkToken.consumed_at.is_(None),
            )
        )
        db.add(
            TelegramLinkToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        await db.commit()

        username = settings.telegram_bot_username.removeprefix("@")
        response.headers["Cache-Control"] = "no-store"
        return TelegramLinkResponse(
            url=f"https://t.me/{username}?start={token}",
            expires_at=expires_at,
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Не удалось создать ссылку Telegram") from None


@router.delete("/me/telegram", status_code=204)
async def disconnect_telegram(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Отключает Telegram; повторный вызов безопасен."""
    try:
        await db.execute(
            delete(TelegramBinding).where(TelegramBinding.user_id == user.id)
        )
        await db.execute(
            delete(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id)
        )
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Не удалось отключить Telegram") from None

    response.headers["Cache-Control"] = "no-store"
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Отозвать текущую действующую сессию без rolling-продления."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")

    try:
        service = AuthSessionService(db)
        if await service.get_user_id(token) is None:
            raise HTTPException(401, "Not authenticated")
        await service.revoke_session(token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(500, "Не удалось завершить сеанс") from None

    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return response
