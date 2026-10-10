from datetime import UTC, datetime

from pydantic import BaseModel, field_validator


class HHAcountTokenData(BaseModel):
    """Внутренний DTO текущего набора OAuth-токенов HH.ru."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime

    @field_validator("access_expires_at")
    @classmethod
    def validate_access_expires_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("access_expires_at must be timezone-aware")
        return value.astimezone(UTC)
