from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.trend import Trend
from app.schemas.common import MessageResponse, TaskResponse
from app.schemas.trend import TrendRead
from app.tasks.trend_tasks import discover_trends

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("", response_model=list[TrendRead])
async def list_trends(
    db: Annotated[AsyncSession, Depends(get_db)],
    niche: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Trend).order_by(desc(Trend.score), desc(Trend.discovered_at))
    if niche:
        stmt = stmt.where(Trend.niche == niche)
    if source:
        stmt = stmt.where(Trend.source == source)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/discover", response_model=TaskResponse)
async def trigger_discovery(niches: list[str] | None = None):
    task = discover_trends.delay(niches)
    return TaskResponse(task_id=task.id, message="Trend discovery started")


@router.get("/{trend_id}", response_model=TrendRead)
async def get_trend(trend_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    trend = await db.get(Trend, trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    return trend
