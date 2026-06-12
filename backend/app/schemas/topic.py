from datetime import datetime

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    niche: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    priority: int = Field(5, ge=1, le=10)
    trend_id: int | None = None


class TopicUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    priority: int | None = None


class TopicRead(BaseModel):
    id: int
    title: str
    niche: str
    description: str | None
    status: str
    priority: int
    trend_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
