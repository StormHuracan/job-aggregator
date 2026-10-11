from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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


@dataclass
class VacancyData:
    source: str
    external_id: str
    title: str
    company_name: str
    area_name: str | None
    salary_from: int | None
    salary_to: int | None
    salary_currency: str | None
    description: str | None
    source_url: str
    published_at: datetime | None
    raw_data: dict[str, Any] | None

    def __post_init__(self) -> None:
        if self.source != "hh":
            raise ValueError("Источник вакансии должен быть 'hh'")

        if self.published_at is not None and self.published_at.tzinfo is None:
            raise ValueError("published_at должен быть timezone-aware")
