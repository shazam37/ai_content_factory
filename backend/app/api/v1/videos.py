import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoRead

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=list[VideoRead])
async def list_videos(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Video).order_by(desc(Video.created_at))
    if status:
        stmt = stmt.where(Video.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{video_id}", response_model=VideoRead)
async def get_video(video_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    return video


@router.get("/{video_id}/download")
async def download_video(video_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    if not video.video_path or not os.path.isfile(video.video_path):
        raise HTTPException(404, "Video file not yet rendered or missing")
    return FileResponse(
        video.video_path,
        media_type="video/mp4",
        filename=f"video_{video_id}.mp4",
    )


@router.get("/{video_id}/thumbnail")
async def get_thumbnail(video_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    if not video.thumbnail_path or not os.path.isfile(video.thumbnail_path):
        raise HTTPException(404, "Thumbnail not available")
    return FileResponse(video.thumbnail_path, media_type="image/jpeg")
