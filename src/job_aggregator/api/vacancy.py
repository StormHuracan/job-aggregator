from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.schemas.vacancy import VacancyListQuery, VacancyListResponse

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.get("")
async def get_vacancies(
    query: Annotated[VacancyListQuery, Query()],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyListResponse:
    vacancy_repository = VacancyRepository(session)
    vacancies, total = await vacancy_repository.list(query)
    return VacancyListResponse(
        items=vacancies,
        total=total,
        limit=query.limit,
        offset=query.offset,
    )
