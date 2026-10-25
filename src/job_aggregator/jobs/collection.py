import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.core.config import Settings
from job_aggregator.db.repositories.saved_search import UserSavedSearchRepository
from job_aggregator.services.saved_searches import SavedSearchCollectionService

logger = logging.getLogger(__name__)


async def run_scheduled_collection(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Запускает сбор для всех пользователей с активными поисками."""
    logger.info("Scheduled collection started")

    # 1. Получаем список ID пользователей (в отдельной короткой сессии)
    try:
        async with session_factory() as session:
            repo = UserSavedSearchRepository(session)
            user_ids = await repo.list_enabled_user_ids()
    except Exception as error:
        logger.error(
            "Failed to load user IDs for scheduled collection: %s",
            type(error).__name__,
        )
        return

    if not user_ids:
        logger.info("No enabled users with saved searches. Collection skipped.")
        return

    logger.info("Found %d users with enabled searches", len(user_ids))

    service = SavedSearchCollectionService(session_factory, settings)
    success_count = 0
    failed_count = 0

    # 2. Последовательно обходим пользователей
    for user_id in user_ids:
        try:
            result = await service.collect_for_user(user_id)
            failed_searches = sum(not search.succeeded for search in result.searches)
            if failed_searches:
                failed_count += 1
            else:
                success_count += 1
            logger.info(
                "User %d collection: failed_searches=%d, searches=%d, "
                "created=%d, updated=%d, skipped=%d, failed=%d, new_matches=%d",
                user_id,
                failed_searches,
                len(result.searches),
                sum(s.created for s in result.searches),
                sum(s.updated for s in result.searches),
                sum(s.skipped for s in result.searches),
                sum(s.failed for s in result.searches),
                result.new_matches,
            )
        except Exception as error:
            # Ловим Exception, чтобы сбой одного пользователя не прерывал остальных.
            # CancelledError не ловится (он BaseException) и пробрасывается наружу.
            failed_count += 1
            logger.error(
                "User %d collection failed: %s",
                user_id,
                type(error).__name__,
            )

    logger.info(
        "Scheduled collection finished: users=%d, succeeded=%d, failed=%d",
        len(user_ids),
        success_count,
        failed_count,
    )


def register_collection_job(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> set[asyncio.Task[None]]:
    """Регистрирует интервальную задачу сбора."""
    active_tasks: set[asyncio.Task[None]] = set()

    async def tracked_collection() -> None:
        task = asyncio.create_task(run_scheduled_collection(session_factory, settings))
        active_tasks.add(task)
        try:
            await task
        finally:
            active_tasks.discard(task)

    scheduler.add_job(
        tracked_collection,
        trigger=IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        id="collect_saved_searches",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "Registered collection job with interval %d minutes",
        settings.scheduler_interval_minutes,
    )
    return active_tasks
