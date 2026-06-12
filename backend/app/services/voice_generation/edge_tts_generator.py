import asyncio
import logging
import os
import subprocess

import edge_tts

from app.core.config import settings
from app.services.voice_generation.base import BaseVoiceGenerator, VoiceGenerationResult

logger = logging.getLogger(__name__)

AVAILABLE_VOICES = {
    "male_us": "en-US-GuyNeural",
    "female_us": "en-US-JennyNeural",
    "male_gb": "en-GB-RyanNeural",
    "female_gb": "en-GB-SoniaNeural",
    "male_au": "en-AU-WilliamNeural",
    "female_au": "en-AU-NatashaNeural",
}


def _get_audio_duration(path: str) -> float:
    """Get audio duration using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", path,
            ],
            capture_output=True, text=True, timeout=10
        )
        import json
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0


class EdgeTTSGenerator(BaseVoiceGenerator):
    """Microsoft Edge TTS — free, high quality, no API key needed."""

    def _resolve_voice(self, voice: str | None) -> str:
        if voice is None:
            return settings.voice_default
        # Accept either a short key like "male_gb" or a full voice name
        return AVAILABLE_VOICES.get(voice, voice)

    async def generate(
        self, text: str, output_path: str, voice: str | None = None
    ) -> VoiceGenerationResult:
        resolved_voice = self._resolve_voice(voice)
        logger.info("Generating TTS: voice=%s chars=%d", resolved_voice, len(text))

        # edge-tts writes to mp3 directly
        mp3_path = output_path if output_path.endswith(".mp3") else output_path + ".mp3"

        communicate = edge_tts.Communicate(text, resolved_voice)
        await communicate.save(mp3_path)

        duration = _get_audio_duration(mp3_path)
        logger.info("TTS complete: %.1fs audio at %s", duration, mp3_path)

        return VoiceGenerationResult(
            audio_path=mp3_path,
            duration_seconds=duration,
            voice_used=resolved_voice,
        )
