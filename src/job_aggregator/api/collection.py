import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.composition import build_collection_service
from job_aggregator.core.config import Settings, get_settings
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.collection_progress import (
    CollectionProgressRepository,
    collection_search_key,
)
from job_aggregator.db.session import get_db_session
from job_aggregator.integrations.hh.dto import HHVacancySearchParams
from job_aggregator.integrations.hh.errors import (
    HHAuthenticationError,
    HHIntegrationError,
    HHTemporaryError,
)
from job_aggregator.schemas.collection import (
    CollectionRunProgressResponse,
    CollectionRunRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collection", tags=["collection"])


@router.post("/hh/run", response_model=CollectionRunProgressResponse)
async def run_collection(
    data: CollectionRunRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> CollectionRunProgressResponse:
    """Собрать страницы от имени владельца и зафиксировать вакансии до ответа."""
    try:
        params = HHVacancySearchParams(
            text=data.text,
            area=(data.area or "").strip() or None,
        )
        progress = await CollectionProgressRepository(session).get_for_update(
            user.id,
            collection_search_key(params.text, params.area),
        )
        if data.restart:
            progress.next_page = 0
            progress.exhausted = False
        if progress.exhausted:
            result = CollectionRunProgressResponse(
                created=0,
                updated=0,
                skipped=0,
                failed=0,
                next_page=progress.next_page,
                exhausted=True,
            )
            await session.commit()
            return result
        params = params.model_copy(update={"page": progress.next_page})
        service = build_collection_service(
            user_id=user.id,
            session=session,
            session_factory=request.app.state.session_factory,
            settings=settings,
        )
        result = await service.collect_pages_with_progress(params, data.pages_limit)
        progress.next_page = result.next_page
        progress.exhausted = result.exhausted
        await session.commit()
        return result
    except asyncio.CancelledError:
        await session.rollback()
        raise
    except Exception as error:
        await session.rollback()
        logger.warning("Manual collection failed: category=%s", type(error).__name__)
        if isinstance(error, HHAuthenticationError):
            code = 409
            detail = "Подключите HH.ru повторно, чтобы запустить сбор"
        elif isinstance(error, HHTemporaryError):
            code = 503
            detail = "HH.ru временно недоступен. Попробуйте позже"
        elif isinstance(error, HHIntegrationError):
            code = 502
            detail = "Не удалось получить вакансии из HH.ru"
        else:
            code = 500
            detail = "Не удалось сохранить результат сбора"
        raise HTTPException(code, detail) from None
