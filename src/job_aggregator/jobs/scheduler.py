from apscheduler.schedulers.asyncio import AsyncIOScheduler

from job_aggregator.core.config import Settings


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Создаёт настроенный, но ещё не запущенный планировщик.

    Каждая job по умолчанию не запускается параллельно сама с собой,
    а пропущенные срабатывания склеиваются в один запуск.
    """

    return AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
        },
    )
