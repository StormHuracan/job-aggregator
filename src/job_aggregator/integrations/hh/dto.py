from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from job_aggregator.schemas.vacancy import VacancyData

HH_MAX_PER_PAGE = 100


class HHVacancySearchParams(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    area: str | None = None
    page: int = Field(default=0, ge=0)
    per_page: int = Field(default=20, ge=1, le=HH_MAX_PER_PAGE)


class HHVacancyPage(BaseModel):
    """Страница нормализованных вакансий; page нумеруется с нуля.

    found и pages описывают весь результат поиска, а не только текущую страницу.
    """

    items: list[VacancyData]
    page: int = Field(ge=0)
    found: int = Field(ge=0)
    pages: int = Field(ge=0)
