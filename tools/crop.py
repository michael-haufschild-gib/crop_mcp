"""crop_image and image_info tools for vision-tools MCP server."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from .grid import render_grid
from .validators import cleanup_temp_dir, validate_coordinates, validate_image_path

# Temp directory for crop outputs — cleaned by LRU eviction
_CROP_DIR = Path(tempfile.gettempdir()) / "vision-tools-crops"
_CROP_DIR_MAX_MB = 50


def image_info(image_path: str) -> dict[str, Any]:
    """Return dimensions, metadata, and a coordinate-grid overlay for an image.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        Dict with width, height, aspect_ratio, file_size_kb, mode,
        pixels_per_percent, longer_axis, and grid_image path.
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

    grid_path = render_grid(img, image_path)

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
) -> dict[str, Any]:
    """Crop a region from an image using normalized 0-1 coordinates.

    Args:
        image_path: Absolute path to the source image.
        x1: Left edge (0.0 = left, 1.0 = right).
        y1: Top edge (0.0 = top, 1.0 = bottom).
        x2: Right edge.
        y2: Bottom edge.
        output_path: Where to save. Defaults to temp directory.
        padding: Extra pixels around the crop region (default 20).

    Returns:
        Dict with output_path, width, height, source dimensions,
        and crop region in both pixel and normalized coordinates.
    """
    path = validate_image_path(image_path)
    validate_coordinates(x1, y1, x2, y2)

    if padding < 0:
        raise ValueError(f"padding must be >= 0, got {padding}")

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

    cropped = img.crop((px_x1, px_y1, px_x2, px_y2))

    # Determine output path
    if output_path:
        out = Path(output_path).expanduser().resolve()
    else:
        _CROP_DIR.mkdir(parents=True, exist_ok=True)
        cleanup_temp_dir(_CROP_DIR, _CROP_DIR_MAX_MB)
        coord_str = f"{x1:.2f}_{y1:.2f}_{x2:.2f}_{y2:.2f}".replace(".", "")
        out = _CROP_DIR / f"crop_{coord_str}_{os.getpid()}.png"

    out.parent.mkdir(parents=True, exist_ok=True)
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
