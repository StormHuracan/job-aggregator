from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.api.dependencies import get_current_user
from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.saved_search import UserSavedSearchRepository
from job_aggregator.db.session import get_db_session
from job_aggregator.schemas.saved_search import (
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
)

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Удаляет поиск текущего владельца; чужой идентификатор не раскрывается."""
    deleted = await UserSavedSearchRepository(session).delete_for_user(
        current_user.id, search_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Search not found")
    await session.commit()


@router.post(
    "", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED
)
async def create_saved_search(
    payload: SavedSearchCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SavedSearchResponse:
    repository = UserSavedSearchRepository(session)
    search = await repository.create(
        user_id=current_user.id,
        name=payload.name,
        text=payload.text,
        area=payload.area,
        min_salary=payload.min_salary,
        max_salary=payload.max_salary,
    )
    await session.commit()
    await session.refresh(search)
    return SavedSearchResponse.model_validate(search)


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SavedSearchResponse]:
    searches = await UserSavedSearchRepository(session).list_for_user(current_user.id)
    return [SavedSearchResponse.model_validate(search) for search in searches]


@router.patch("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    payload: SavedSearchUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SavedSearchResponse:
    repository = UserSavedSearchRepository(session)
    search = await repository.set_enabled(
        user_id=current_user.id,
        search_id=search_id,
        is_enabled=payload.is_enabled,
    )
    if search is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Search not found"
        )

    await session.commit()
    await session.refresh(search)
    return SavedSearchResponse.model_validate(search)
