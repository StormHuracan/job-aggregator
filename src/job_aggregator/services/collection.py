import logging
from collections.abc import Awaitable, Callable

from job_aggregator.db.repositories.vacancy import (
    VacancyRepository,
    VacancySaveError,
    VacancyUpsertResult,
)
from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.dto import HHVacancyPage, HHVacancySearchParams
from job_aggregator.schemas.collection import (
    CollectionRunProgressResponse,
    CollectionRunResponse,
)
from job_aggregator.schemas.vacancy import VacancyData

logger = logging.getLogger(__name__)


class VacancyCollectionService:
    """Сбор вакансий с частичным успехом при ошибках данных."""

    def __init__(
        self,
        client: HHClient,
        repository: VacancyRepository,
        on_saved: Callable[
            [VacancyData, VacancyUpsertResult],
            Awaitable[None],
        ]
        | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        self._on_saved = on_saved

    async def collect(self, params: HHVacancySearchParams) -> CollectionRunResponse:
        """Собирает ровно одну страницу. Оставлен для обратной совместимости."""
        logger.info("Collection started")
        try:
            page = await self._client.search_vacancies(params)
            result = await self._process_page_items(page)
            self._log_completed(self._received_count(page), result)
            return result
        except Exception as error:
            logger.error("Collection failed: %s", type(error).__name__)
            raise

    async def collect_pages(
        self, params: HHVacancySearchParams, pages_limit: int
    ) -> CollectionRunResponse:
        """Собирает до pages_limit страниц (максимальное число запросов)."""
        progress = await self.collect_pages_with_progress(params, pages_limit)
        return CollectionRunResponse(**progress.model_dump())

    async def collect_pages_with_progress(
        self, params: HHVacancySearchParams, pages_limit: int
    ) -> CollectionRunProgressResponse:
        """Собирает страницы и возвращает следующую позицию, не делая commit.

        Наличие знакомых вакансий не завершает обход; число запросов ограничено
        pages_limit независимо от количества созданных записей.
        """
        if pages_limit <= 0:
            raise ValueError("pages_limit должен быть больше нуля")

        logger.info("Collection started (pages_limit=%d)", pages_limit)
        result = CollectionRunProgressResponse(
            created=0,
            updated=0,
            skipped=0,
            failed=0,
            next_page=params.page,
            exhausted=False,
        )
        current_page = params.page
        total_received = 0

        try:
            for _ in range(pages_limit):
                # Не мутируем исходный DTO, создаем копию с нужным page
                page_params = params.model_copy(update={"page": current_page})
                page = await self._client.search_vacancies(page_params)
                received = self._received_count(page)
                total_received += received

                page_result = await self._process_page_items(page)
                result.created += page_result.created
                result.updated += page_result.updated
                result.skipped += page_result.skipped
                result.failed += page_result.failed
                result.next_page = current_page + 1

                # Останавливаемся, если страница пустая или это была последняя страница
                if not received:
                    result.exhausted = True
                    break
                if current_page + 1 >= page.pages:
                    result.exhausted = True
                    break

                current_page += 1

            self._log_completed(total_received, result)
            return result
        except Exception as error:
            logger.error("Collection failed: %s", type(error).__name__)
            raise

    async def _process_page_items(self, page: HHVacancyPage) -> CollectionRunResponse:
        """Обрабатывает вакансии на одной странице, возвращая счетчики."""
        result = CollectionRunResponse(
            created=0,
            updated=0,
            skipped=0,
            failed=max(0, self._received_count(page) - len(page.items)),
        )
        for vacancy in page.items:
            try:
                outcome = await self._repository.upsert(vacancy)
            except VacancySaveError:
                logger.warning("Vacancy data rejected during collection")
                result.failed += 1
                continue

            if self._on_saved is not None:
                await self._on_saved(vacancy, outcome)

            match outcome:
                case VacancyUpsertResult.CREATED:
                    result.created += 1
                case VacancyUpsertResult.UPDATED:
                    result.updated += 1
                case VacancyUpsertResult.UNCHANGED:
                    result.skipped += 1
                case _:
                    raise ValueError("Неизвестный результат сохранения вакансии")
        return result

    @staticmethod
    def _received_count(page: HHVacancyPage) -> int:
        return len(page.items) if page.received_count is None else page.received_count

    def _log_completed(self, received: int, result: CollectionRunResponse) -> None:
        logger.info(
            "Collection completed: received=%d created=%d updated=%d "
            "skipped=%d failed=%d",
            received,
            result.created,
            result.updated,
            result.skipped,
            result.failed,
        )
