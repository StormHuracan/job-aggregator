from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.schemas.statistics import (
    AreaVacancyCount,
    VacancyStatisticsResponse,
)
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


@router.get("/stats")
async def get_vacancy_statistics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyStatisticsResponse:
    """Статистика по всем сохранённым вакансиям: количество, средняя, топ городов."""
    try:
        statistics = await VacancyRepository(session).get_statistics()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(500, "Не удалось загрузить статистику") from None
    return VacancyStatisticsResponse(
        total_vacancies=statistics.total_vacancies,
        salary_currency="RUR",
        salary_sample_size=statistics.salary_sample_size,
        average_salary=statistics.average_salary,
        top_areas=[
            AreaVacancyCount(area_name=name, vacancies_count=count)
            for name, count in statistics.top_areas
        ],
    )
