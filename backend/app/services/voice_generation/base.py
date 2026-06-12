from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VoiceGenerationResult:
    audio_path: str
    duration_seconds: float
    voice_used: str


class BaseVoiceGenerator(ABC):
    @abstractmethod
    async def generate(self, text: str, output_path: str, voice: str | None = None) -> VoiceGenerationResult:
        ...
