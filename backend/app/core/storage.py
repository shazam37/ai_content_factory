import os
import uuid
from pathlib import Path

from app.core.config import settings


def _ensure(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def audio_path(filename: str | None = None) -> str:
    base = _ensure(settings.storage_audio)
    if filename is None:
        filename = f"{uuid.uuid4()}.mp3"
    return str(base / filename)


def image_path(filename: str | None = None) -> str:
    base = _ensure(settings.storage_images)
    if filename is None:
        filename = f"{uuid.uuid4()}.png"
    return str(base / filename)


def video_path(filename: str | None = None) -> str:
    base = _ensure(settings.storage_videos)
    if filename is None:
        filename = f"{uuid.uuid4()}.mp4"
    return str(base / filename)


def thumbnail_path(filename: str | None = None) -> str:
    base = _ensure(settings.storage_thumbnails)
    if filename is None:
        filename = f"{uuid.uuid4()}.jpg"
    return str(base / filename)


def file_exists(path: str) -> bool:
    return os.path.isfile(path)


def file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except OSError:
        return 0.0
