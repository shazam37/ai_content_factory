"""
Topic-relevant stock photos from loremflickr.com.
Free, no API key required. Single-keyword search returns real Flickr photos.
Multi-keyword URLs cause 500 errors on their side — use one keyword only.
"""
import asyncio
import io
import logging

import httpx
from PIL import Image

from app.services.image_generation.base import BaseImageGenerator, ImageGenerationResult

logger = logging.getLogger(__name__)

# Maps substrings found in image prompts → reliable loremflickr single keywords.
# Only use keywords confirmed to return HTTP 200 at 720×1280.
_KEYWORD_MAP: list[tuple[str, str]] = [
    # Physics / Quantum
    ("quantum",      "science"),
    ("particle",     "science"),
    ("photon",       "science"),
    ("electron",     "science"),
    ("entangle",     "science"),
    ("nuclear",      "science"),
    ("radiation",    "science"),
    ("magnetic",     "science"),
    # Brain / Biology
    ("neuron",       "science"),
    ("synapse",      "science"),
    ("brain",        "science"),
    ("action potential", "science"),
    ("dna",          "nature"),
    ("virus",        "nature"),
    ("bacteria",     "nature"),
    ("evolution",    "nature"),
    ("biology",      "nature"),
    ("cell",         "nature"),
    # Space
    ("galaxy",       "space"),
    ("universe",     "space"),
    ("planet",       "space"),
    ("asteroid",     "space"),
    ("telescope",    "space"),
    ("orbit",        "space"),
    ("cosmos",       "space"),
    ("space",        "space"),
    ("black hole",   "space"),
    # Technology / Computer
    ("computer",     "computer"),
    ("algorithm",    "computer"),
    ("software",     "computer"),
    ("program",      "computer"),
    ("robot",        "technology"),
    ("internet",     "technology"),
    ("network",      "technology"),
    ("data",         "technology"),
    ("cryptograph",  "technology"),
    # Laboratory
    ("laboratory",   "laboratory"),
    ("experiment",   "laboratory"),
    ("microscope",   "laboratory"),
    ("chemical",     "laboratory"),
    ("laser",        "laboratory"),
    ("detector",     "laboratory"),
    ("fiber optic",  "laboratory"),
    # Ocean / Environment
    ("ocean",        "ocean"),
    ("sea",          "ocean"),
    ("climate",      "nature"),
    ("forest",       "nature"),
    ("mountain",     "mountain"),
    # History / People
    ("einstein",     "research"),
    ("newton",       "research"),
    ("scientist",    "research"),
    ("ancient",      "city"),
    ("history",      "city"),
    ("war",          "city"),
    ("empire",       "city"),
    ("revolution",   "city"),
    ("electricity",  "technology"),
    ("electric",     "technology"),
    ("energy",       "technology"),
]

_DEFAULT_KEYWORD = "science"


def _pick_keyword(prompt: str) -> str:
    pl = prompt.lower()
    for fragment, keyword in _KEYWORD_MAP:
        if fragment in pl:
            return keyword
    return _DEFAULT_KEYWORD


def _save_photo(content: bytes, output_path: str, width: int, height: int) -> None:
    img = Image.open(io.BytesIO(content)).convert("RGB")
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    img.save(output_path, "PNG", optimize=True)


class LoremFlickrGenerator(BaseImageGenerator):
    """Gets topic-relevant real photos from loremflickr.com. Free, no sign-up."""

    def __init__(self) -> None:
        from app.services.image_generation.ffmpeg_slide_generator import FFmpegSlideGenerator
        self._fallback = FFmpegSlideGenerator()

    async def generate(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> ImageGenerationResult:
        keyword = _pick_keyword(prompt)
        # lock= gives a consistent but varied image per scene (avoids all scenes looking identical)
        lock = abs(hash(prompt)) % 9000 + 1
        # Request at 720x1280 (loremflickr sweet spot) → Pillow upscales to target
        fetch_w, fetch_h = 720, 1280
        url = f"https://loremflickr.com/{fetch_w}/{fetch_h}/{keyword}?lock={lock}"
        logger.info("LoremFlickr: keyword=%r lock=%d", keyword, lock)

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content = resp.content

            await asyncio.to_thread(_save_photo, content, output_path, width, height)
            logger.info("LoremFlickr saved: %s (keyword=%r)", output_path, keyword)
            return ImageGenerationResult(
                image_path=output_path,
                width=width,
                height=height,
                prompt_used=prompt,
            )

        except Exception as exc:
            logger.warning("LoremFlickr failed (%s) — using slide fallback", exc)
            return await self._fallback.generate(prompt, output_path, width, height)
