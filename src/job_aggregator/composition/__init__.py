from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings
from job_aggregator.db.repositories.vacancy import (
    VacancyRepository,
    VacancyUpsertResult,
)
from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.schemas.vacancy import VacancyData
from job_aggregator.services.collection import VacancyCollectionService
from job_aggregator.services.hh_requests import AuthorizedHHAPIClient


def build_collection_service(
    user_id: int,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    on_saved: Callable[[VacancyData, VacancyUpsertResult], Awaitable[None]]
    | None = None,
) -> VacancyCollectionService:
    vacancy_repository = VacancyRepository(session=session)

    authorized_client = AuthorizedHHAPIClient(
        session_factory=session_factory,
        user_id=user_id,
        allow_token_refresh=settings.hh_allow_token_refresh,
        client_id=settings.hh_client_id,
        client_secret=settings.hh_client_secret,
    )

    client = HHClient(authorized_client)

    if on_saved is None:
        return VacancyCollectionService(client=client, repository=vacancy_repository)
    return VacancyCollectionService(
        client=client, repository=vacancy_repository, on_saved=on_saved
    )
