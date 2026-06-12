"""
Generates abstract gradient background images via Pillow.
Used as a zero-dependency fallback when no image API is configured.
The caption text is added separately via caption.py — this module only
produces the background visual.
"""
import asyncio
import logging
import math
import random

from PIL import Image, ImageDraw

from app.services.image_generation.base import BaseImageGenerator, ImageGenerationResult

logger = logging.getLogger(__name__)

# Niche → (dark_color, mid_color, accent_color)
NICHE_PALETTES: dict[str, tuple] = {
    "science": ((5, 15, 50), (15, 50, 140), (80, 180, 255)),
    "history": ((35, 18, 8), (100, 55, 18), (220, 160, 60)),
    "programming": ((5, 22, 5), (12, 70, 25), (50, 220, 80)),
    "ai": ((18, 5, 38), (60, 18, 110), (160, 80, 255)),
    "trivia": ((5, 28, 38), (12, 85, 110), (60, 200, 240)),
    "default": ((8, 8, 28), (25, 25, 75), (100, 140, 220)),
}

_KEYWORDS = list(NICHE_PALETTES.keys())


def _detect_niche(prompt: str) -> str:
    p = prompt.lower()
    for niche in _KEYWORDS:
        if niche in p:
            return niche
    return "default"


def _make_background(
    prompt: str,
    output_path: str,
    width: int,
    height: int,
) -> None:
    niche = _detect_niche(prompt)
    dark, mid, accent = NICHE_PALETTES[niche]

    rng = random.Random(hash(prompt) & 0xFFFFFF)

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Vertical gradient: dark → mid
    for y in range(height):
        t = y / height
        r = int(dark[0] + (mid[0] - dark[0]) * t)
        g = int(dark[1] + (mid[1] - dark[1]) * t)
        b = int(dark[2] + (mid[2] - dark[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Large soft accent circle (top-right glow)
    cx = int(width * rng.uniform(0.55, 0.85))
    cy = int(height * rng.uniform(0.08, 0.30))
    radius = int(width * rng.uniform(0.45, 0.65))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    steps = 40
    for s in range(steps):
        t = 1 - s / steps
        alpha = int(55 * t * t)
        r2 = int(radius * (1 - s / steps * 0.85))
        gd.ellipse(
            [cx - r2, cy - r2, cx + r2, cy + r2],
            fill=(accent[0], accent[1], accent[2], alpha),
        )
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Diagonal light rays from top-right corner
    num_rays = rng.randint(4, 7)
    for i in range(num_rays):
        angle = math.radians(rng.uniform(200, 280))
        ray_len = int(height * rng.uniform(0.5, 1.1))
        x0, y0 = cx, cy
        x1 = x0 + int(math.cos(angle) * ray_len)
        y1 = y0 + int(math.sin(angle) * ray_len)
        alpha = rng.randint(12, 28)
        ray_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ray_draw = ImageDraw.Draw(ray_img)
        ray_draw.line([(x0, y0), (x1, y1)], fill=(*accent, alpha), width=rng.randint(60, 140))
        img = Image.alpha_composite(img.convert("RGBA"), ray_img).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Small floating dots (particles)
    for _ in range(rng.randint(12, 22)):
        px = rng.randint(0, width)
        py = rng.randint(0, height)
        pr = rng.randint(3, 14)
        alpha = rng.randint(40, 120)
        dot_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dot_draw = ImageDraw.Draw(dot_img)
        dot_draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(*accent, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), dot_img).convert("RGB")

    # Bottom vignette (blends into caption area)
    vig = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    vig_start = int(height * 0.55)
    for y in range(vig_start, height):
        a = int(180 * (y - vig_start) / (height - vig_start))
        vd.line([(0, y), (width, y)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")

    img.save(output_path, "PNG", optimize=True)


class FFmpegSlideGenerator(BaseImageGenerator):
    """Generates abstract gradient background images. Caption is added separately."""

    async def generate(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> ImageGenerationResult:
        await asyncio.to_thread(_make_background, prompt, output_path, width, height)
        logger.debug("Slide background generated: %s", output_path)
        return ImageGenerationResult(image_path=output_path, width=width, height=height, prompt_used=prompt)
