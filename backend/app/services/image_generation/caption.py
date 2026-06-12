"""
Burns YouTube-Shorts-style caption onto an image (in-place).

Layout:
  • Bottom ~45% of frame: dark semi-transparent background bar
  • Inside the bar: bold white text, centred, 2–3 lines max
  • Heavy black stroke so text pops on any background colour
  • Text positioned to survive the 8% Ken Burns crop (130px safe margin)
"""
import textwrap

from PIL import Image, ImageDraw, ImageFont

_FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_FONT_SIZE = 74           # large — takes up ~60% of frame width at 1080p
_MAX_CHARS_PER_LINE = 18  # keep lines punchy; wraps earlier for bigger text feel
_MAX_LINES = 3
_BOTTOM_SAFE = 140        # px from bottom — survives Ken Burns 8% crop


def add_caption(image_path: str, text: str) -> None:
    """Burn narration caption into the lower portion of the image. Modifies in-place."""
    if not text or not text.strip():
        return

    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    # ── Dark gradient bar — covers bottom 45% of frame ───────────────────────
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    bar_top = int(h * 0.55)
    for y in range(bar_top, h):
        alpha = int(230 * ((y - bar_top) / (h - bar_top)) ** 0.6)
        ov_draw.line([(0, y), (w, y)], fill=(0, 0, 10, alpha))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # ── Load font ─────────────────────────────────────────────────────────────
    try:
        font = ImageFont.truetype(_FONT_PATH, _FONT_SIZE)
    except (IOError, OSError):
        font = ImageFont.load_default()

    # ── Wrap text ─────────────────────────────────────────────────────────────
    lines = textwrap.wrap(text.strip(), width=_MAX_CHARS_PER_LINE)[:_MAX_LINES]
    if not lines:
        return

    # ── Measure and position ─────────────────────────────────────────────────
    line_gap = int(_FONT_SIZE * 0.22)
    line_h = _FONT_SIZE + line_gap
    total_text_h = len(lines) * line_h - line_gap

    # Bottom of text block sits at BOTTOM_SAFE px from the frame bottom
    text_bottom = h - _BOTTOM_SAFE
    text_top = text_bottom - total_text_h

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        y = text_top + i * line_h

        # ── Heavy black stroke (6px, 8 directions) for contrast on any bg ────
        stroke = 6
        for dx in range(-stroke, stroke + 1, 2):
            for dy in range(-stroke, stroke + 1, 2):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))

        # ── White fill ────────────────────────────────────────────────────────
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    img.convert("RGB").save(image_path, "PNG", optimize=True)
