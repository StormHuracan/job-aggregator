from contextlib import asynccontextmanager

from fastapi import FastAPI

from job_aggregator.api.router import api_router
from job_aggregator.core.config import get_settings
from job_aggregator.core.logging import configure_logging
from job_aggregator.db.session import create_engine_and_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine, session_factory = create_engine_and_factory(settings.database_url)

    app.state.engine = engine
    app.state.session_factory = session_factory

    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()
