import logging

from job_aggregator.db.repositories.vacancy import (
    VacancyRepository,
    VacancySaveError,
    VacancyUpsertResult,
)
from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.dto import HHVacancySearchParams
from job_aggregator.schemas.collection import CollectionRunResponse

logger = logging.getLogger(__name__)


class VacancyCollectionService:
    """Сбор одной страницы с частичным успехом только при ошибках данных."""

    def __init__(self, client: HHClient, repository: VacancyRepository) -> None:
        self._client = client
        self._repository = repository

    async def collect(self, params: HHVacancySearchParams) -> CollectionRunResponse:
        """Возвращает счётчики; commit и фатальные ошибки — у вызывающей стороны."""
        logger.info("Collection started")
        try:
            return await self._collect(params)
        except Exception as error:
            logger.error("Collection failed: %s", type(error).__name__)
            raise

    async def _collect(self, params: HHVacancySearchParams) -> CollectionRunResponse:
        page = await self._client.search_vacancies(params)
        result = CollectionRunResponse(created=0, updated=0, skipped=0, failed=0)
        for vacancy in page.items:
            try:
                outcome = await self._repository.upsert(vacancy)
            except VacancySaveError:
                logger.warning("Vacancy data rejected during collection")
                result.failed += 1
                continue

            match outcome:
                case VacancyUpsertResult.CREATED:
                    result.created += 1
                case VacancyUpsertResult.UPDATED:
                    result.updated += 1
                case VacancyUpsertResult.UNCHANGED:
                    result.skipped += 1
                case _:
                    raise ValueError("Неизвестный результат сохранения вакансии")
        logger.info(
            "Collection completed: received=%d created=%d updated=%d "
            "skipped=%d failed=%d",
            len(page.items),
            result.created,
            result.updated,
            result.skipped,
            result.failed,
        )
        return result
