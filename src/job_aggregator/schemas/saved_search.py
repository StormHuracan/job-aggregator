from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SavedSearchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=255)
    area: str | None = Field(default=None, max_length=255)
    min_salary: int | None = Field(default=None, ge=0)
    max_salary: int | None = Field(default=None, ge=0)

    @field_validator("name", "text", mode="before")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("area", mode="before")
    @classmethod
    def strip_area(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_salary_range(self) -> "SavedSearchCreate":
        if (
            self.min_salary is not None
            and self.max_salary is not None
            and self.min_salary > self.max_salary
        ):
            raise ValueError("min_salary не может превышать max_salary")
        return self


class SavedSearchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool


class SavedSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    text: str
    area: str | None
    min_salary: int | None
    max_salary: int | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
