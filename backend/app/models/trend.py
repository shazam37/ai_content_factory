from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # reddit, rss, google
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    niche: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Trend {self.source}:{self.niche} '{self.keyword[:40]}'>"
