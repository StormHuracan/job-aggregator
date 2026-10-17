from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserSettingsResponse(BaseModel):
    """Персональные настройки пользователя в ответе API."""

    default_area: str | None
    default_pages_limit: int


class UserSettingsUpdate(BaseModel):
    """Частичное обновление настроек пользователя.

    Обновляются только явно переданные поля; default_area: null очищает регион.
    """

    model_config = ConfigDict(extra="forbid")

    default_area: str | None = None
    default_pages_limit: int | None = Field(default=None, gt=0)

    @field_validator("default_area")
    @classmethod
    def validate_default_area(cls, value: str | None) -> str | None:
        if value is None:
            return None

        stripped = value.strip()
        if not stripped:
            raise ValueError("default_area не может быть пустым")
        if len(stripped) > 255:
            raise ValueError("default_area не длиннее 255 символов")
        return stripped


class CurrentUserResponse(BaseModel):
    """Данные текущего пользователя для личного кабинета, без токенов."""

    id: int
    display_name: str
    hh_connected: bool
    access_expires_at: datetime | None
    new_matches_count: int = Field(ge=0)
    settings: UserSettingsResponse

    @field_validator("access_expires_at")
    @classmethod
    def validate_access_expires_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("access_expires_at must be timezone-aware")
        return value.astimezone(UTC)
