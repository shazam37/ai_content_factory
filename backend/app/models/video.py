from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class VideoStatus:
    QUEUED = "queued"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_IMAGES = "generating_images"
    ASSEMBLING = "assembling"
    RENDERED = "rendered"
    FAILED = "failed"


class PublishStatus:
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topics.id"), nullable=False
    )
    script_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scripts.id"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(50), default=VideoStatus.QUEUED)

    # File paths
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_paths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Render metadata
    render_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    topic = relationship("Topic", back_populates="videos")
    script = relationship("Script", back_populates="videos")
    publishing_records = relationship("PublishingRecord", back_populates="video")

    def __repr__(self) -> str:
        return f"<Video #{self.id} status={self.status}>"


class PublishingRecord(Base):
    __tablename__ = "publishing_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("videos.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_video_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=PublishStatus.PENDING)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    video = relationship("Video", back_populates="publishing_records")
    analytics = relationship("Analytics", back_populates="publishing_record")


class Analytics(Base):
    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publishing_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("publishing_records.id"), nullable=False
    )
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_avg_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    retention_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    publishing_record = relationship("PublishingRecord", back_populates="analytics")
