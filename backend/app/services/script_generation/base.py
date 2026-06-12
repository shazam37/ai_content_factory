from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GeneratedScript:
    hook: str
    main_content: str
    cta: str
    title: str
    description: str
    hashtags: list[str]
    scenes: list[dict]
    estimated_duration_seconds: int
    model_used: str


class BaseScriptGenerator(ABC):
    @abstractmethod
    async def generate(self, topic: str, niche: str, style: str = "educational") -> GeneratedScript:
        ...
