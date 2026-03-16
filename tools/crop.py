"""crop_image and image_info tools for vision-tools MCP server."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Supported image extensions (lowercase)
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def validate_image_path(image_path: str) -> Path:
    """Validate that the image path exists and is a readable image file.

    Returns the resolved Path on success.
    Raises ValueError with a helpful message on failure.
    """
    path = Path(image_path).expanduser().resolve()

    if not path.exists():
        # Try to give a helpful suggestion
        parent = path.parent
        if not parent.exists():
            raise ValueError(
                f"Image not found: {image_path}\n"
                f"The directory '{parent}' does not exist either.\n"
                f"Hint: Use an absolute path like /Users/you/screenshots/image.png"
            )
        # Check if there's a similar file
        similar = [f.name for f in parent.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        if similar:
            suggestions = ", ".join(similar[:5])
            raise ValueError(
                f"Image not found: {image_path}\nImages in that directory: {suggestions}"
            )
        raise ValueError(
            f"Image not found: {image_path}\nHint: Make sure you're using the full absolute path."
        )

    if not path.is_file():
        raise ValueError(f"Not a file: {image_path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format: '{path.suffix}'\n"
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    return path


def validate_coordinates(x1: float, y1: float, x2: float, y2: float) -> None:
    """Validate normalized coordinates are within 0-1 and properly ordered.

    Raises ValueError with a helpful message explaining the coordinate system.
    """
    coords = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    for name, val in coords.items():
        if not isinstance(val, (int, float)):
            raise ValueError(
                f"'{name}' must be a number, got {type(val).__name__}.\n"
                f"Coordinates use a 0-1 scale: 0.0 = left/top edge, 1.0 = right/bottom edge."
            )
        if val < 0.0 or val > 1.0:
            raise ValueError(
                f"'{name}' = {val} is out of range.\n"
                f"All coordinates must be between 0.0 and 1.0.\n"
                f"  (0,0) = top-left corner\n"
                f"  (1,1) = bottom-right corner\n"
                f"Example: To crop the bottom-right quarter, use x1=0.5, y1=0.5, x2=1.0, y2=1.0"
            )

    if x1 >= x2:
        raise ValueError(
            f"x1 ({x1}) must be less than x2 ({x2}).\n"
            f"x1 is the LEFT edge, x2 is the RIGHT edge.\n"
            f"Hint: Did you swap them? Try x1={min(x1, x2)}, x2={max(x1, x2)}"
        )

    if y1 >= y2:
        raise ValueError(
            f"y1 ({y1}) must be less than y2 ({y2}).\n"
            f"y1 is the TOP edge, y2 is the BOTTOM edge.\n"
            f"Hint: Did you swap them? Try y1={min(y1, y2)}, y2={max(y1, y2)}"
        )


# Grid temp directory — survives across calls within a session, cleaned by OS
_GRID_DIR = Path(tempfile.gettempdir()) / "vision-tools-grids"

# Index of the .5 gridline in the 1-9 range (gets special yellow color)
_GRID_MIDPOINT_INDEX = 5

# Grid colors
_CYAN = (0, 255, 255)
_MAGENTA = (255, 0, 255)
_YELLOW = (200, 200, 0)  # darker yellow for contrast on black pills

# Font search order: macOS → Linux common → Pillow default
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
    draw.rectangle([x, y, x + pw, y + ph], fill=(0, 0, 0, 200))
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
    color = _YELLOW if is_half else _CYAN
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


def _render_grid(img: Image.Image, source_path: str) -> str:
    """Render a coordinate grid overlay on a copy of the image.

    10% lines in cyan (bold, labeled), 5% lines in subtle magenta.
    Labels on all four edges for easy reading from any position.

    Returns the path to the grid-annotated image (in a temp directory).
    """
    _GRID_DIR.mkdir(parents=True, exist_ok=True)

    w, h = img.size
    overlay_img = img.convert("L").convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(16, int(min(w, h) * 0.05))
    font = _get_font(font_size)
    pad = 2
    minor_line = (*_MAGENTA, 60)

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
    grid_path = str(_GRID_DIR / f"grid_{stem}.png")
    result.save(grid_path, "PNG")
    return grid_path


def image_info(image_path: str) -> dict:
    """Return dimensions, metadata, and a coordinate-grid overlay for an image.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        Dict with width, height, aspect_ratio, pixels_per_percent,
        longer_axis, and grid_image path.
    """
    path = validate_image_path(image_path)

    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(
            f"Could not open image: {path}\n"
            f"Error: {e}\n"
            f"The file exists but may be corrupted or not a valid image."
        ) from e

    width, height = img.size
    file_size = path.stat().st_size
    longer_axis = "x" if width >= height else "y"

    grid_path = _render_grid(img, image_path)

    return {
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4) if height > 0 else 0,
        "file_size_kb": round(file_size / 1024, 1),
        "mode": img.mode,
        "pixels_per_percent": {
            "x": round(width * 0.01, 1),
            "y": round(height * 0.01, 1),
        },
        "longer_axis": longer_axis,
        "grid_image": grid_path,
    }


def crop_image(
    image_path: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    output_path: str | None = None,
    padding: int = 20,
) -> dict:
    """Crop a region from an image using normalized 0-1 coordinates.

    Args:
        image_path: Absolute path to the source image.
        x1: Left edge (0.0 = left, 1.0 = right).
        y1: Top edge (0.0 = top, 1.0 = bottom).
        x2: Right edge.
        y2: Bottom edge.
        output_path: Where to save. Defaults to {image_dir}/crop_{x1}_{y1}.png.
        padding: Extra pixels around the crop region (default 20).

    Returns:
        Dict with output_path, width, height of the cropped image.
    """
    # Validate inputs
    path = validate_image_path(image_path)
    validate_coordinates(x1, y1, x2, y2)

    if padding < 0:
        raise ValueError(f"padding must be >= 0, got {padding}")

    # Open image
    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(
            f"Could not open image: {path}\n"
            f"Error: {e}\n"
            f"The file exists but may be corrupted or not a valid image."
        ) from e

    # Convert to RGB if needed (handles RGBA, palette, etc.)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    width, height = img.size

    # Convert normalized coordinates to pixel coordinates
    px_x1 = int(x1 * width)
    px_y1 = int(y1 * height)
    px_x2 = int(x2 * width)
    px_y2 = int(y2 * height)

    # Apply padding, clamped to image bounds
    px_x1 = max(0, px_x1 - padding)
    px_y1 = max(0, px_y1 - padding)
    px_x2 = min(width, px_x2 + padding)
    px_y2 = min(height, px_y2 + padding)

    # Ensure we have at least a 1x1 crop
    if px_x2 - px_x1 < 1 or px_y2 - px_y1 < 1:
        raise ValueError(
            f"Crop region is too small (would be {px_x2 - px_x1}x{px_y2 - px_y1} pixels).\n"
            f"Image size: {width}x{height}. Try using a larger region."
        )

    # Crop
    cropped = img.crop((px_x1, px_y1, px_x2, px_y2))

    # Determine output path
    if output_path:
        out = Path(output_path).expanduser().resolve()
    else:
        # Generate default name in the same directory as source
        coord_str = f"{x1:.2f}_{y1:.2f}_{x2:.2f}_{y2:.2f}".replace(".", "")
        out = path.parent / f"crop_{coord_str}.png"

    # Ensure output directory exists
    out.parent.mkdir(parents=True, exist_ok=True)

    # Save as PNG (lossless, always works)
    cropped.save(str(out), "PNG")

    return {
        "output_path": str(out),
        "width": cropped.size[0],
        "height": cropped.size[1],
        "source_width": width,
        "source_height": height,
        "crop_region_px": {
            "x1": px_x1,
            "y1": px_y1,
            "x2": px_x2,
            "y2": px_y2,
        },
        "crop_region_normalized": {
            "x1": round(px_x1 / width, 4),
            "y1": round(px_y1 / height, 4),
            "x2": round(px_x2 / width, 4),
            "y2": round(px_y2 / height, 4),
        },
    }
