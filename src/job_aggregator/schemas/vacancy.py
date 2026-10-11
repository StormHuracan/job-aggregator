from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VacancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    title: str
    company_name: str | None
    area_name: str | None
    salary_from: int | None
    salary_to: int | None
    salary_currency: str | None
    description: str | None
    source_url: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VacancyListQuery(BaseModel):
    company: str | None = None
    text: str | None = None
    area: str | None = None
    salary_from: int | None = Field(default=None, ge=0)
    salary_to: int | None = Field(default=None, ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_salary_range(self) -> Self:
        if self.salary_from is not None and self.salary_to is not None:
            if self.salary_from > self.salary_to:
                raise ValueError("salary_from не может быть больше чем salary_to")
        return self
