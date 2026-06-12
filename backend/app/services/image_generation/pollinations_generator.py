"""
AI image generation via Pollinations.ai — free, no API key required.
Uses the Flux model. Expect 15-45s per image.
Falls back to the slide generator if the API fails.
"""
import io
import logging
import urllib.parse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.image_generation.base import BaseImageGenerator, ImageGenerationResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://image.pollinations.ai/prompt"


def _save_image(content: bytes, output_path: str, width: int, height: int) -> None:
    from PIL import Image

    img = Image.open(io.BytesIO(content)).convert("RGB")
    img = img.resize((width, height), Image.LANCZOS)
    img.save(output_path, "PNG")


class PollinationsGenerator(BaseImageGenerator):
    """Generates AI images using Pollinations.ai (Flux). Free, no sign-up needed."""

    def __init__(self) -> None:
        from app.services.image_generation.ffmpeg_slide_generator import FFmpegSlideGenerator
        self._fallback = FFmpegSlideGenerator()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
    async def _fetch(self, prompt: str, width: int, height: int) -> bytes:
        # Enhance for vertical cinematic look
        enhanced = f"{prompt}, vertical 9:16, cinematic, detailed, vivid colors"
        encoded = urllib.parse.quote(enhanced)
        url = f"{_BASE_URL}/{encoded}"
        params = {
            "width": width,
            "height": height,
            "model": "flux",
            "nologo": "true",
            "seed": abs(hash(prompt)) % 999983,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.get(url, params=params, follow_redirects=True)
            response.raise_for_status()
            return response.content

    async def generate(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> ImageGenerationResult:
        import asyncio

        logger.info("Pollinations image: %s...", prompt[:70])
        try:
            content = await self._fetch(prompt, width, height)
            await asyncio.to_thread(_save_image, content, output_path, width, height)
            logger.info("Pollinations saved: %s", output_path)
            return ImageGenerationResult(image_path=output_path, width=width, height=height, prompt_used=prompt)
        except Exception as exc:
            logger.warning("Pollinations failed (%s) — using slide fallback", exc)
            return await self._fallback.generate(prompt, output_path, width, height)
