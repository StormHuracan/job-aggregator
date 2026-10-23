from typing import Annotated

from pydantic import BaseModel, StringConstraints

AreaName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class HHAreaSuggestion(BaseModel):
    id: Annotated[str, StringConstraints(pattern=r"^\d+$")]
    name: AreaName
    parent_name: AreaName | None = None
