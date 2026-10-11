from fastapi import APIRouter, Depends

from job_aggregator.api.dependencies import get_token_service
from job_aggregator.schemas.hh_auth import HHAuthStatusResponse
from job_aggregator.services.tokens import TokenService

router = APIRouter(prefix="/auth/hh", tags=["auth"])


@router.get("/status", response_model=HHAuthStatusResponse)
async def hh_status(
    token_service: TokenService = Depends(get_token_service),
) -> HHAuthStatusResponse:
    tokens = await token_service.get_current()
    if tokens is None:
        return HHAuthStatusResponse(connected=False, access_expires_at=None)
    return HHAuthStatusResponse(
        connected=True,
        access_expires_at=tokens.access_expires_at,
    )
