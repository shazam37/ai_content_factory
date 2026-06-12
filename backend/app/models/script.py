from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ScriptStatus:
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topics.id"), nullable=False
    )

    # Script content
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    main_content: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)
    scenes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    # Video metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # Quality
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Generation metadata
    model_used: Mapped[str | None] = mapped_column(String(200), nullable=True)
    voice_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[str] = mapped_column(String(50), default=ScriptStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    topic = relationship("Topic", back_populates="scripts")
    videos = relationship("Video", back_populates="script")

    def __repr__(self) -> str:
        return f"<Script #{self.id} topic={self.topic_id} score={self.quality_score}>"
