from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.session import get_db_session
from job_aggregator.services.tokens import TokenService


def get_token_service(session: AsyncSession = Depends(get_db_session)) -> TokenService:
    return TokenService(session)