from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImageGenerationResult:
    image_path: str
    width: int
    height: int
    prompt_used: str


class BaseImageGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> ImageGenerationResult:
        ...
