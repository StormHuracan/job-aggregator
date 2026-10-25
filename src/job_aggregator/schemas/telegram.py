from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TelegramLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    expires_at: datetime


class TelegramStatusResponse(BaseModel):
    enabled: bool
    connected: bool
