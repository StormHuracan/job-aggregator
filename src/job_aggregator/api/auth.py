from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated


from job_aggregator.api.dependencies import get_token_service
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.client import HHAPIClient
from job_aggregator.integrations.hh.errors import HHPermanentRequestError
from job_aggregator.schemas.hh_auth import HHAuthStatusResponse
from job_aggregator.schemas.hh_token import HHAccountTokenData
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


@router.get("/auth/hh/callback")
async def hh_oauth_callback(
        # Обязательные query-параметры
        code: Annotated[str, Query()],
        state: Annotated[str, Query()],
        # Внедрение зависимостей (адаптируйте под ваши get_* провайдеры)
        db_session: Depends(get_db_session),
        oauth_client: Depends(get_hh_oauth_client),
        auth_service: Depends(get_auth_session_service),
) -> dict:  # Скорректируйте возвращаемый тип (например, Response с кукой сессии или DTO)

    # 1. Одноразово потребляем state.
    # Метод внутри делает select ... with_for_update() и выставляет consumed_at
    state_is_valid = await auth_service.consume_oauth_state(state)

    # 2. Немедленно фиксируем транзакцию для state, чтобы предотвратить параллельный повторный запрос
    await db_session.commit()

    # Если state невалиден, обмен токенов даже не запускается
    if not state_is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used OAuth state.",
        )

    # Определяем redirect_uri, который зарегистрирован в HH и использовался при генерации линка
    # Обычно берется из конфигурации или динамически собирается из request.url
    redirect_uri = "https://your-domain.com"

    try:
        # 3. Обмениваем временный code на токены через HHOAuthClient
        token_data: HHAccountTokenData = await oauth_client.exchange_code(
            code=code,
            redirect_uri=redirect_uri
        )

        # 4. Инициализируем HHAPIClient для получения профиля.
        # Передаем полученные токены и отключаем автообновление (так как это первый вход)
        api_client = HHAPIClient(
            tokens=token_data,
            allow_token_refresh=False,
            client_id=oauth_client._client_id,
            client_secret=oauth_client._client_secret,
        )

        # 5. Получаем нормализованный профиль пользователя HHUserProfile
        user_profile = await api_client.get_current_user()

    except HHPermanentRequestError as ex:
        # Ошибки интеграции HH или невалидного профиля возвращаем как 400 Bad Request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate via HeadHunter."
        ) from ex

    # Далее следует ваша бизнес-логика (Use Case / Handler):
    # Например:
    # user = await get_or_create_user_by_hh_id(db_session, user_profile.hh_user_id, user_profile.display_name)
    # session_token = await auth_service.create_session(user.id)
    # await db_session.commit()

    return {
        "hh_user_id": user_profile.hh_user_id,
        "display_name": user_profile.display_name,
    }