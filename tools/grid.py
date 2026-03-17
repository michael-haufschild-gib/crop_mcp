"""Grid overlay rendering for vision-tools MCP server."""

from __future__ import annotations

import itertools
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .validators import cleanup_temp_dir

# Grid output directory — survives across calls, cleaned by OS or LRU eviction
_GRID_DIR = Path(tempfile.gettempdir()) / "vision-tools-grids"

# LRU eviction threshold for grid temp directory (megabytes)
_GRID_DIR_MAX_MB = 50

# Maximum dimension for grid rendering (pixels). Larger images are thumbnailed.
# 4000x4000 RGBA x 2 copies ≈ 128MB — keeps memory reasonable.
_GRID_MAX_DIM = 4000

_file_counter = itertools.count()

# Index of the .5 gridline in the 1-9 range (gets special yellow color)
_GRID_MIDPOINT_INDEX = 5

# Desaturation factor: 0.0 = full grayscale, 1.0 = original color.
# 0.2 keeps just enough color to identify UI elements while reducing
# visual noise so gridlines remain clearly visible.
_SATURATION_FACTOR = 0.2

# Sharpening factor: 1.0 = no change, >1.0 = sharper.
# Crisper edges help distinguish gridline positions against the image.
_SHARPNESS_FACTOR = 1.5

# Grid colors
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
YELLOW = (200, 200, 0)  # darker yellow for contrast on black pills

# Font search order: macOS -> Linux common -> Pillow default
_FONT_PATHS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFMono-Regular.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a monospace font at the given size, with cross-platform fallback."""
    for font_path in _FONT_PATHS:
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_label_pill(
    draw: ImageDraw.ImageDraw,
    pos: tuple[int, int],
    label: str,
    color: tuple[int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    pad: int,
) -> None:
    """Draw a black pill background with colored text at pos (x, y)."""
    bbox = font.getbbox(label)
    pw = (bbox[2] - bbox[0]) + pad * 2
    ph = (bbox[3] - bbox[1]) + pad * 2
    x, y = pos
    draw.rectangle((x, y, x + pw, y + ph), fill=(0, 0, 0, 200))
    draw.text((x + pad, y + pad), label, fill=(*color, 255), font=font)


def _draw_major_gridline(
    draw: ImageDraw.ImageDraw,
    i: int,
    w: int,
    h: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    pad: int,
) -> None:
    """Draw a single major (10%) gridline with labels on all four edges."""
    frac = i * 0.1
    x = int(frac * w)
    y = int(frac * h)

    is_half = i == _GRID_MIDPOINT_INDEX
    color = YELLOW if is_half else CYAN
    line_fill = (*color, 150 if is_half else 120)
    line_width = 3 if is_half else 2

    label = f".{i}"
    bbox = font.getbbox(label)
    pill_w = (bbox[2] - bbox[0]) + pad * 2
    pill_h = (bbox[3] - bbox[1]) + pad * 2

    x_label_x = x - pill_w // 2
    y_label_y = y - pill_h // 2

    # Gridlines with gaps for labels
    draw.line([(x, pill_h + 4), (x, h - pill_h - 4)], fill=line_fill, width=line_width)
    draw.line([(pill_w + 4, y), (w - pill_w - 4, y)], fill=line_fill, width=line_width)

    # Labels on all four edges
    _draw_label_pill(draw, (x_label_x, 2), label, color, font, pad)
    _draw_label_pill(draw, (x_label_x, h - pill_h - 2), label, color, font, pad)
    _draw_label_pill(draw, (2, y_label_y), label, color, font, pad)
    _draw_label_pill(draw, (w - pill_w - 2, y_label_y), label, color, font, pad)


def render_grid(img: Image.Image, source_path: str) -> str:
    """Render a coordinate grid overlay on a copy of the image.

    10% lines in cyan (bold, labeled), 5% lines in subtle magenta.
    Labels on all four edges for easy reading from any position.

    Args:
        img: Source image (not modified).
        source_path: Original file path (used to derive output filename).

    Returns:
        Path to the grid-annotated image (in a temp directory).
    """
    _GRID_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_temp_dir(_GRID_DIR, _GRID_DIR_MAX_MB)

    # Thumbnail if either dimension exceeds the memory budget
    if img.size[0] > _GRID_MAX_DIM or img.size[1] > _GRID_MAX_DIM:
        img = img.copy()
        img.thumbnail((_GRID_MAX_DIM, _GRID_MAX_DIM), Image.LANCZOS)

    w, h = img.size
    desaturated = ImageEnhance.Color(img.convert("RGB")).enhance(_SATURATION_FACTOR)
    sharpened = ImageEnhance.Sharpness(desaturated).enhance(_SHARPNESS_FACTOR)
    overlay_img = sharpened.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(16, int(min(w, h) * 0.05))
    font = _get_font(font_size)
    pad = 2
    minor_line = (*MAGENTA, 60)

    # 5% lines: subtle magenta midpoint references
    for i in range(1, 20):
        if i % 2 == 0:
            continue
        frac = i * 0.05
        x = int(frac * w)
        y = int(frac * h)
        draw.line([(x, 0), (x, h)], fill=minor_line, width=1)
        draw.line([(0, y), (w, y)], fill=minor_line, width=1)

    # 10% lines: bold, labeled on all edges
    for i in range(1, 10):
        _draw_major_gridline(draw, i, w, h, font, pad)

    result = Image.alpha_composite(overlay_img, overlay)

    stem = Path(source_path).stem
    grid_path = str(_GRID_DIR / f"grid_{stem}_{next(_file_counter)}.png")
    result.save(grid_path, "PNG")
    return grid_path
