import asyncio
import logging
import re

import httpx

from app.core.config import settings
from app.services.image_generation.base import BaseImageGenerator, ImageGenerationResult
from app.services.image_generation.ffmpeg_slide_generator import FFmpegSlideGenerator

logger = logging.getLogger(__name__)

PEXELS_API = "https://api.pexels.com/v1"


def _extract_keywords(prompt: str) -> str:
    """Pull the most descriptive words from a long image prompt."""
    stop = {"a", "an", "the", "of", "in", "on", "at", "for", "with", "and", "or"}
    words = re.sub(r"[^a-zA-Z\s]", "", prompt).split()
    keywords = [w for w in words if w.lower() not in stop and len(w) > 3]
    return " ".join(keywords[:5])


class PexelsImageGenerator(BaseImageGenerator):
    """Fetches real stock photos from Pexels API. Requires PEXELS_API_KEY."""

    def __init__(self) -> None:
        self._fallback = FFmpegSlideGenerator()

    async def generate(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> ImageGenerationResult:
        if not settings.pexels_api_key:
            logger.warning("Pexels API key not set — falling back to slide generator")
            return await self._fallback.generate(prompt, output_path, width, height)

        query = _extract_keywords(prompt)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{PEXELS_API}/search",
                    params={"query": query, "per_page": 5, "orientation": "portrait"},
                    headers={"Authorization": settings.pexels_api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                photos = data.get("photos", [])
                if not photos:
                    raise ValueError("No photos returned")

                photo = photos[0]
                img_url = photo["src"].get("portrait") or photo["src"]["original"]

                img_resp = await client.get(img_url)
                img_resp.raise_for_status()

            def _save(content: bytes, path: str) -> None:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(content)).convert("RGB")
                img = img.resize((width, height), Image.LANCZOS)
                img.save(path, "PNG")

            await asyncio.to_thread(_save, img_resp.content, output_path)
            logger.info("Pexels image saved: %s (query=%r)", output_path, query)

            return ImageGenerationResult(
                image_path=output_path,
                width=width,
                height=height,
                prompt_used=prompt,
            )

        except Exception as e:
            logger.warning("Pexels failed (%s) — falling back to slide generator", e)
            return await self._fallback.generate(prompt, output_path, width, height)


def get_image_generator() -> BaseImageGenerator:
    if settings.image_provider in ("loremflickr", "pollinations"):
        from app.services.image_generation.loremflickr_generator import LoremFlickrGenerator
        return LoremFlickrGenerator()
    if settings.image_provider == "pexels":
        return PexelsImageGenerator()
    return FFmpegSlideGenerator()
