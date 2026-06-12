import asyncio
import logging
import subprocess
import json

from app.services.voice_generation.base import BaseVoiceGenerator, VoiceGenerationResult

logger = logging.getLogger(__name__)

# Map voice name keywords to gTTS locale/tld combos
_VOICE_TO_TLD = {
    "gb": "co.uk",
    "au": "com.au",
    "ca": "ca",
    "in": "co.in",
}


def _get_audio_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0


def _resolve_tld(voice: str | None) -> str:
    """Pick a Google TTS regional accent from a voice name hint."""
    if not voice:
        return "com"
    v = voice.lower()
    for key, tld in _VOICE_TO_TLD.items():
        if key in v:
            return tld
    return "com"


class GTTSGenerator(BaseVoiceGenerator):
    """Google Text-to-Speech — no API key, works in any network environment."""

    async def generate(
        self, text: str, output_path: str, voice: str | None = None
    ) -> VoiceGenerationResult:
        from gtts import gTTS

        tld = _resolve_tld(voice)
        mp3_path = output_path if output_path.endswith(".mp3") else output_path + ".mp3"

        logger.info("Generating gTTS audio: tld=%s chars=%d", tld, len(text))

        tts = gTTS(text=text, lang="en", tld=tld, slow=False)
        await asyncio.to_thread(tts.save, mp3_path)

        duration = _get_audio_duration(mp3_path)
        logger.info("gTTS complete: %.1fs -> %s", duration, mp3_path)

        return VoiceGenerationResult(
            audio_path=mp3_path,
            duration_seconds=duration,
            voice_used=f"gtts-en-{tld}",
        )
