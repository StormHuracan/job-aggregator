from fastapi import FastAPI

from job_aggregator.api.router import api_router
from job_aggregator.core.config import get_settings
from job_aggregator.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)
    app.include_router(api_router)
    return app


app = create_app()
