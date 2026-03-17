"""Generate deterministic test images for live MCP QA.

Each image has known ground-truth properties documented in live_qa_checklist.md.
Run with: make live-qa  (or: python tests/generate_live_images.py)

Output directory: tests/live_qa_images/ (gitignored)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT_DIR = Path(__file__).parent / "live_qa_images"

# --- Ground truth constants (referenced by checklist) ---

QUADRANT_COLORS: dict[str, tuple[int, int, int]] = {
    "top_left": (255, 0, 0),  # #FF0000 red
    "top_right": (0, 255, 0),  # #00FF00 green
    "bottom_left": (0, 0, 255),  # #0000FF blue
    "bottom_right": (255, 255, 0),  # #FFFF00 yellow
}

BAR_COLORS: list[tuple[int, int, int]] = [
    (255, 0, 0),  # #FF0000
    (255, 128, 0),  # #FF8000
    (255, 255, 0),  # #FFFF00
    (0, 128, 0),  # #008000
    (0, 0, 255),  # #0000FF
    (128, 0, 255),  # #8000FF
]

MARKER_COLOR: tuple[int, int, int] = (255, 0, 0)  # #FF0000
LARGE_BG: tuple[int, int, int] = (255, 255, 255)  # #FFFFFF


def generate_quadrants(size: int = 400) -> Path:
    """400x400 image with 4 solid-color quadrants.

    Layout (normalized coords):
        TL (0,0)-(0.5,0.5) = #FF0000
        TR (0.5,0)-(1.0,0.5) = #00FF00
        BL (0,0.5)-(0.5,1.0) = #0000FF
        BR (0.5,0.5)-(1.0,1.0) = #FFFF00
    """
    half = size // 2
    img = Image.new("RGB", (size, size))
    img.paste(Image.new("RGB", (half, half), QUADRANT_COLORS["top_left"]), (0, 0))
    img.paste(Image.new("RGB", (half, half), QUADRANT_COLORS["top_right"]), (half, 0))
    img.paste(Image.new("RGB", (half, half), QUADRANT_COLORS["bottom_left"]), (0, half))
    img.paste(Image.new("RGB", (half, half), QUADRANT_COLORS["bottom_right"]), (half, half))
    path = OUTPUT_DIR / "quadrants_400x400.png"
    img.save(str(path))
    return path


def generate_color_bars(width: int = 600, height: int = 100) -> Path:
    """600x100 image with 6 equal-width vertical color stripes.

    Each stripe is 100px wide. Colors left-to-right:
        #FF0000, #FF8000, #FFFF00, #008000, #0000FF, #8000FF
    """
    img = Image.new("RGB", (width, height))
    stripe_w = width // len(BAR_COLORS)
    for i, color in enumerate(BAR_COLORS):
        img.paste(Image.new("RGB", (stripe_w, height), color), (i * stripe_w, 0))
    path = OUTPUT_DIR / "color_bars_600x100.png"
    img.save(str(path))
    return path


def generate_large_with_markers(width: int = 2000, height: int = 1000) -> Path:
    """2000x1000 white image with colored markers at known positions.

    Markers (40x40 red squares):
        Center:       (0.50, 0.50) — pixel (1000, 500)
        Top-left:     (0.25, 0.25) — pixel (500, 250)
        Bottom-right: (0.75, 0.75) — pixel (1500, 750)
    """
    img = Image.new("RGB", (width, height), LARGE_BG)
    draw = ImageDraw.Draw(img)
    marker_half = 20  # 40x40 squares

    markers = [
        (int(width * 0.50), int(height * 0.50)),  # center
        (int(width * 0.25), int(height * 0.25)),  # top-left quarter
        (int(width * 0.75), int(height * 0.75)),  # bottom-right quarter
    ]
    for cx, cy in markers:
        draw.rectangle(
            (cx - marker_half, cy - marker_half, cx + marker_half, cy + marker_half),
            fill=MARKER_COLOR,
        )

    path = OUTPUT_DIR / "large_markers_2000x1000.png"
    img.save(str(path))
    return path


def main() -> None:
    """Generate all test images."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    paths = [
        generate_quadrants(),
        generate_color_bars(),
        generate_large_with_markers(),
    ]

    for p in paths:
        print(f"  {p.name}", file=sys.stderr)  # noqa: T201
    print(f"Generated {len(paths)} images in {OUTPUT_DIR}", file=sys.stderr)  # noqa: T201


if __name__ == "__main__":
    main()
