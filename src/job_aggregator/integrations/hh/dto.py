from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

HH_MAX_PER_PAGE = 100


class HHVacancySearchParams(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    area: str | None = None
    page: int = Field(default=0, ge=0)
    per_page: int = Field(default=20, ge=1, le=HH_MAX_PER_PAGE)
