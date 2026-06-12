from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TrendBase(BaseModel):
    source: str
    keyword: str
    niche: str
    score: float = 0.0
    url: str | None = None
    raw_data: dict[str, Any] | None = None


class TrendCreate(TrendBase):
    pass


class TrendRead(TrendBase):
    id: int
    discovered_at: datetime

    model_config = {"from_attributes": True}
