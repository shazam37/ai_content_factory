from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VideoRead(BaseModel):
    id: int
    topic_id: int
    script_id: int
    status: str
    audio_path: str | None
    image_paths: list[str] | None
    video_path: str | None
    thumbnail_path: str | None
    render_time_seconds: float | None
    duration_seconds: float | None
    file_size_mb: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoRenderRequest(BaseModel):
    script_id: int
    voice: str | None = None
    image_provider: str | None = None


class AnalyticsRead(BaseModel):
    id: int
    publishing_record_id: int
    views: int
    likes: int
    comments: int
    shares: int
    watch_time_avg_seconds: float | None
    retention_rate: float | None
    recorded_at: datetime

    model_config = {"from_attributes": True}
