from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.user import User
from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHIntegrationError,
    HHTemporaryError,
)
from job_aggregator.schemas.hh_area import HHAreaSuggestion
from job_aggregator.services.hh_requests import AuthorizedHHAPIClient

router = APIRouter(prefix="/hh", tags=["hh"])


def get_hh_area_client(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> HHClient:
    return HHClient(
        AuthorizedHHAPIClient(
            session_factory=request.app.state.session_factory,
            user_id=user.id,
            allow_token_refresh=settings.hh_allow_token_refresh,
            client_id=settings.hh_client_id,
            client_secret=settings.hh_client_secret,
        )
    )


@router.get("/areas", response_model=list[HHAreaSuggestion])
async def suggest_areas(
    text: Annotated[str, Query(min_length=2, max_length=255)],
    user: User = Depends(get_current_user),
    client: HHClient = Depends(get_hh_area_client),
) -> list[HHAreaSuggestion]:
    """Подсказки от имени текущего пользователя; токены не выдаются UI."""
    text = text.strip()
    if len(text) < 2:
        raise HTTPException(422, "Введите хотя бы две буквы названия региона")
    try:
        return await client.suggest_areas(text)
    except HHAuthenticationError:
        raise HTTPException(
            409, "Подключите HH.ru повторно, чтобы выбрать регион"
        ) from None
    except HHTemporaryError:
        raise HTTPException(
            503, "Не удалось загрузить регионы. Попробуйте позже"
        ) from None
    except HHIntegrationError:
        raise HTTPException(502, "Не удалось загрузить регионы") from None
