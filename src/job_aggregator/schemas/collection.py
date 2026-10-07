from pydantic import BaseModel, Field, field_validator


class CollectionRunRequest(BaseModel):
    text: str
    area: str | None
    pages_limit: int = Field(gt=0)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text не может быть пустым")
        return value


class CollectionRunResponse(BaseModel):
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
