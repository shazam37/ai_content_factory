"""
Generates styled text slide images using Pillow (no GPU needed).
Each slide has a gradient background + centered text + niche accent color.
Perfect for zero-dependency Phase 1 operation.
"""
import asyncio
import hashlib
import logging
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.image_generation.base import BaseImageGenerator, ImageGenerationResult

logger = logging.getLogger(__name__)

NICHE_PALETTES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "science": ((10, 20, 60), (30, 60, 150)),
    "history": ((40, 20, 10), (120, 60, 20)),
    "programming": ((5, 25, 5), (15, 80, 30)),
    "ai": ((20, 5, 40), (70, 20, 120)),
    "trivia": ((5, 30, 40), (15, 90, 120)),
    "default": ((10, 10, 30), (30, 30, 80)),
}


def _detect_niche(prompt: str) -> str:
    prompt_lower = prompt.lower()
    for niche in NICHE_PALETTES:
        if niche in prompt_lower:
            return niche
    return "default"


def _draw_gradient(draw: ImageDraw.ImageDraw, w: int, h: int, top: tuple, bottom: tuple) -> None:
    for y in range(h):
        ratio = y / h
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def _make_slide(text: str, output_path: str, width: int, height: int, niche: str) -> None:
    top_color, bottom_color = NICHE_PALETTES.get(niche, NICHE_PALETTES["default"])

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    _draw_gradient(draw, width, height, top_color, bottom_color)

    # Try to load a system font, fall back to default
    font_size = max(40, width // 18)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    # Word-wrap text
    max_chars = max(20, width // (font_size // 2))
    wrapped = textwrap.fill(text, width=max_chars)
    lines = wrapped.split("\n")

    # Compute total text block height
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = int(font_size * 0.4)
    total_h = sum(line_heights) + line_spacing * (len(lines) - 1)
    y = (height - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (width - lw) // 2

        # Drop shadow
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

        y += line_heights[i] + line_spacing

    # Accent bar at bottom
    bar_h = max(6, height // 120)
    accent = (100, 180, 255) if niche == "science" else (255, 180, 60)
    draw.rectangle([(0, height - bar_h), (width, height)], fill=accent)

    img.save(output_path, "PNG", optimize=True)


class FFmpegSlideGenerator(BaseImageGenerator):
    """Generates styled slide images via Pillow. Zero GPU, zero network calls."""

    async def generate(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> ImageGenerationResult:
        niche = _detect_niche(prompt)
        # Truncate prompt to fit on slide (first ~80 chars look best)
        display_text = prompt[:120] if len(prompt) > 120 else prompt

        await asyncio.to_thread(_make_slide, display_text, output_path, width, height, niche)
        logger.debug("Slide generated: %s", output_path)

        return ImageGenerationResult(
            image_path=output_path,
            width=width,
            height=height,
            prompt_used=prompt,
        )
