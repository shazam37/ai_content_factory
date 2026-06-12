from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "content_factory",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.trend_tasks",
        "app.tasks.generation_tasks",
        "app.tasks.video_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.trend_tasks.*": {"queue": "default"},
        "app.tasks.generation_tasks.*": {"queue": "generation"},
        "app.tasks.video_tasks.*": {"queue": "video"},
    },
    beat_schedule={
        "discover-trends-hourly": {
            "task": "app.tasks.trend_tasks.discover_trends",
            "schedule": crontab(minute=0),
        },
    },
)
