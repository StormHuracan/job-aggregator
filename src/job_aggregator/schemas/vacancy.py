from datetime import datetime

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
