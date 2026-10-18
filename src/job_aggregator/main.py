from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from job_aggregator.api.router import api_router
from job_aggregator.core.config import get_settings
from job_aggregator.core.logging import configure_logging
from job_aggregator.db.session import create_engine_and_factory
from job_aggregator.jobs.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine, session_factory = create_engine_and_factory(settings.database_url)

    app.state.engine = engine
    app.state.session_factory = session_factory

    scheduler: AsyncIOScheduler | None = None
    if settings.scheduler_enabled:
        scheduler = create_scheduler(settings)
        scheduler.start()
    app.state.scheduler = scheduler

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()
