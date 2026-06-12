from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VideoAssemblyResult:
    video_path: str
    thumbnail_path: str
    duration_seconds: float
    file_size_mb: float


class BaseVideoAssembler(ABC):
    @abstractmethod
    async def assemble(
        self,
        audio_path: str,
        image_paths: list[str],
        output_path: str,
        thumbnail_path: str,
        scene_durations: list[float] | None = None,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
    ) -> VideoAssemblyResult:
        ...
