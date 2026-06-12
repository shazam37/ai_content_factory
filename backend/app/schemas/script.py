from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SceneSchema(BaseModel):
    index: int
    text: str
    image_prompt: str
    duration_seconds: float = 5.0


class ScriptRead(BaseModel):
    id: int
    topic_id: int
    hook: str
    main_content: str
    cta: str
    scenes: list[SceneSchema] | None
    title: str
    description: str
    hashtags: list[str] | None
    quality_score: float | None
    quality_feedback: dict[str, Any] | None
    model_used: str | None
    voice_style: str | None
    estimated_duration_seconds: int | None
    version: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ScriptApprove(BaseModel):
    approved: bool
    feedback: str | None = None
