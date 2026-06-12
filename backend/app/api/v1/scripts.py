from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.script import Script, ScriptStatus
from app.schemas.common import TaskResponse
from app.schemas.script import ScriptApprove, ScriptRead
from app.tasks.video_tasks import render_video

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("", response_model=list[ScriptRead])
async def list_scripts(
    db: Annotated[AsyncSession, Depends(get_db)],
    topic_id: int | None = Query(None),
    status: str | None = Query(None),
    min_score: float | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Script).order_by(desc(Script.created_at))
    if topic_id:
        stmt = stmt.where(Script.topic_id == topic_id)
    if status:
        stmt = stmt.where(Script.status == status)
    if min_score is not None:
        stmt = stmt.where(Script.quality_score >= min_score)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{script_id}", response_model=ScriptRead)
async def get_script(script_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    return script


@router.post("/{script_id}/approve", response_model=ScriptRead)
async def approve_script(
    script_id: int,
    body: ScriptApprove,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    script.status = ScriptStatus.APPROVED if body.approved else ScriptStatus.REJECTED
    await db.commit()
    await db.refresh(script)
    return script


@router.post("/{script_id}/render", response_model=TaskResponse)
async def trigger_render(
    script_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    voice: str | None = Query(None),
    image_provider: str | None = Query(None),
):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(404, "Script not found")
    if script.status != ScriptStatus.APPROVED:
        raise HTTPException(400, "Script must be approved before rendering")
    task = render_video.delay(script_id, voice, image_provider)
    return TaskResponse(task_id=task.id, message=f"Video render started for script {script_id}")
