from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.topic import Topic, TopicStatus
from app.schemas.common import MessageResponse, TaskResponse
from app.schemas.topic import TopicCreate, TopicRead, TopicUpdate
from app.tasks.generation_tasks import generate_script

router = APIRouter(prefix="/topics", tags=["topics"])


@router.post("", response_model=TopicRead, status_code=201)
async def create_topic(
    body: TopicCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = Topic(**body.model_dump())
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


@router.get("", response_model=list[TopicRead])
async def list_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    niche: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Topic).order_by(desc(Topic.priority), desc(Topic.created_at))
    if status:
        stmt = stmt.where(Topic.status == status)
    if niche:
        stmt = stmt.where(Topic.niche == niche)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{topic_id}", response_model=TopicRead)
async def get_topic(topic_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    return topic


@router.patch("/{topic_id}", response_model=TopicRead)
async def update_topic(
    topic_id: int,
    body: TopicUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(topic, field, value)
    await db.commit()
    await db.refresh(topic)
    return topic


@router.post("/{topic_id}/generate-script", response_model=TaskResponse)
async def trigger_script_generation(
    topic_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    voice: str | None = Query(None),
):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    task = generate_script.delay(topic_id, voice)
    return TaskResponse(task_id=task.id, message=f"Script generation started for topic {topic_id}")


@router.delete("/{topic_id}", response_model=MessageResponse)
async def delete_topic(topic_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    await db.delete(topic)
    await db.commit()
    return MessageResponse(message="Topic deleted")
