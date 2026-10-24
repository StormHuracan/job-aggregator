import asyncio
from contextlib import asynccontextmanager, suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from job_aggregator.api.router import api_router
from job_aggregator.core.config import get_settings
from job_aggregator.core.logging import configure_logging
from job_aggregator.db.session import create_engine_and_factory
from job_aggregator.jobs.scheduler import create_scheduler
from job_aggregator.jobs.telegram import run_telegram_bot
from job_aggregator.services.otp_login import OTPLoginService


async def _expire_otp_flows(service: OTPLoginService) -> None:
    while True:
        await asyncio.sleep(30)
        await service.prune()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    if settings.telegram_enabled and (
        not settings.telegram_bot_token or not settings.telegram_bot_username
    ):
        raise RuntimeError("Telegram is enabled, but its token or username is missing.")

    engine, session_factory = create_engine_and_factory(settings.database_url)

    app.state.engine = engine
    app.state.session_factory = session_factory

    scheduler: AsyncIOScheduler | None = None
    if settings.scheduler_enabled:
        scheduler = create_scheduler(settings)
        scheduler.start()
    app.state.scheduler = scheduler
    cleanup = asyncio.create_task(_expire_otp_flows(app.state.otp_logins))

    telegram_task = None

    if settings.telegram_enabled:
        telegram_task = asyncio.create_task(run_telegram_bot(session_factory, settings))

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown()

        if telegram_task is not None:
            telegram_task.cancel()
            with suppress(asyncio.CancelledError):
                await telegram_task

        cleanup.cancel()
        try:
            with suppress(asyncio.CancelledError):
                await cleanup
            await app.state.otp_logins.close()
        finally:
            await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.otp_logins = OTPLoginService()
    app.include_router(api_router)
    return app


app = create_app()
