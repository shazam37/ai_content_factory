from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TopicStatus:
    PENDING = "pending"
    SELECTED = "selected"
    GENERATING = "generating"
    DONE = "done"
    REJECTED = "rejected"


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    niche: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=TopicStatus.PENDING)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    trend_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trends.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trend = relationship("Trend", foreign_keys=[trend_id])
    scripts = relationship("Script", back_populates="topic", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="topic")

    def __repr__(self) -> str:
        return f"<Topic #{self.id} [{self.niche}] '{self.title[:40]}'>"
