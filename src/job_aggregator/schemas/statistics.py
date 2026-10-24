from typing import Literal

from pydantic import BaseModel, Field


class AreaVacancyCount(BaseModel):
    """Город или регион и число сохранённых вакансий в нём."""

    area_name: str
    vacancies_count: int = Field(gt=0)


class VacancyStatisticsResponse(BaseModel):
    """Статистика по всем сохранённым вакансиям.

    Средняя зарплата считается только по рублёвым вакансиям с полной вилкой.
    """

    total_vacancies: int = Field(ge=0)
    salary_currency: Literal["RUR"]
    salary_sample_size: int = Field(ge=0)
    average_salary: float | None
    top_areas: list[AreaVacancyCount]
