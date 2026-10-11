from datetime import datetime

from pydantic import BaseModel


class HHAuthStatusResponse(BaseModel):
    connected: bool
    access_expires_at: datetime | None
