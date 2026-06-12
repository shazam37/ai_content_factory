from app.services.voice_generation.base import BaseVoiceGenerator


def get_voice_generator() -> BaseVoiceGenerator:
    from app.core.config import settings

    provider = settings.voice_provider.lower()
    if provider == "edge_tts":
        from app.services.voice_generation.edge_tts_generator import EdgeTTSGenerator
        return EdgeTTSGenerator()

    from app.services.voice_generation.gtts_generator import GTTSGenerator
    return GTTSGenerator()
