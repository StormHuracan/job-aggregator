from fastapi import APIRouter

from job_aggregator.api.auth import router as auth_router
from job_aggregator.api.health import router as health_router
from job_aggregator.api.vacancy import router as vacancy_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(vacancy_router)
