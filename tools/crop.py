"""crop_image and image_info tools for vision-tools MCP server."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict, Unpack

from .edge_detail import Point, edge_checks
from .grid import render_crop_rulers, render_grid
from .measure import FillBounds, measure_fill
from .validators import (
    cleanup_temp_dir,
    pixel_edge,
    read_image,
    validate_coordinates,
    validate_image_path,
)

if TYPE_CHECKING:
    from PIL import Image

    from .edge_detail import Box

__all__ = ["crop_image", "image_info"]

# Temp directory for crop outputs — cleaned by LRU eviction
_CROP_DIR = Path(tempfile.gettempdir()) / "vision-tools-crops"
_CROP_DIR_MAX_MB = 50


class PixelsPerPercent(TypedDict):
    """Pixels displaced per 1% coordinate error on each axis."""

    x: float
    y: float


class PixelRegion(TypedDict):
    """Crop region in absolute pixel coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int


class NormalizedRegion(TypedDict):
    """Crop region in normalized 0-1 coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float


class ImageInfoResult(TypedDict):
    """Return type for image_info."""

    width: int
    height: int
    aspect_ratio: float
    file_size_kb: float
    mode: str
    pixels_per_percent: PixelsPerPercent
    longer_axis: str
    grid_image: str
    measured_fill: NotRequired[FillBounds]


class CropResult(TypedDict):
    """Return type for crop_image."""

    output_path: str
    width: int
    height: int
    source_width: int
    source_height: int
    grid_image: NotRequired[str]
    detail_image: NotRequired[str]
    edge_checks_px: NotRequired[dict[str, list[Point]]]
    traced_edges_px: NotRequired[dict[str, int]]
    traced_edges_normalized: NotRequired[dict[str, float]]
    crop_region_px: PixelRegion
    crop_region_normalized: NormalizedRegion


def _validate_padding(padding: int) -> None:
    """Validate crop padding before pixel arithmetic."""
    if isinstance(padding, bool) or not isinstance(padding, int):
        raise ValueError(f"padding must be a non-negative integer, got {type(padding).__name__}")
    if padding < 0:
        raise ValueError(f"padding must be >= 0, got {padding}")


def image_info(image_path: str, measure_at: list[float] | None = None) -> ImageInfoResult:
    """Return dimensions, metadata, and a coordinate-grid overlay for an image.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        Dict with width, height, aspect_ratio, file_size_kb, mode,
        pixels_per_percent, longer_axis, and grid_image path.
    """
    path = validate_image_path(image_path)

    img = read_image(path)

    width, height = img.size
    mode = img.mode
    file_size = path.stat().st_size
    longer_axis = "x" if width >= height else "y"

    measured = measure_fill(img, measure_at) if measure_at is not None else None
    result: ImageInfoResult = {
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4) if height > 0 else 0,
        "file_size_kb": round(file_size / 1024, 1),
        "mode": mode,
        "pixels_per_percent": {
            "x": width / 100,
            "y": height / 100,
        },
        "longer_axis": longer_axis,
        "grid_image": render_grid(img, image_path),
    }
    if measured is not None:
        result["measured_fill"] = measured
    return result


class CropView(TypedDict, total=False):
    """Display options beyond the original seven crop parameters."""

    show_grid: bool
    show_detail: bool


def crop_image(
    image_path: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    output_path: str | None = None,
    padding: int = 20,
    **view: Unpack[CropView],
) -> CropResult:
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

    _validate_padding(padding)

    img = read_image(path)
    if img.has_transparency_data and img.mode != "RGBA":
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    width, height = img.size

    # Convert normalized coordinates to pixel coordinates
    px_x1 = pixel_edge(x1, width)
    px_y1 = pixel_edge(y1, height)
    px_x2 = pixel_edge(x2, width)
    px_y2 = pixel_edge(y2, height)

    proposed = (px_x1, px_y1, px_x2, px_y2)

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
        if out == path or (out.exists() and out.samefile(path)):
            raise ValueError("Choose an output path different from the source image.")
    else:
        _CROP_DIR.mkdir(parents=True, exist_ok=True)
        cleanup_temp_dir(_CROP_DIR, _CROP_DIR_MAX_MB)
        coord_str = f"{x1:.2f}_{y1:.2f}_{x2:.2f}_{y2:.2f}".replace(".", "")
        out = _CROP_DIR / f"crop_{coord_str}_{uuid.uuid4().hex[:8]}.png"

    out.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(str(out), "PNG")

    result: CropResult = {
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
            "x1": px_x1 / width,
            "y1": px_y1 / height,
            "x2": px_x2 / width,
            "y2": px_y2 / height,
        },
    }
    if view.get("show_grid") or view.get("show_detail"):
        result["grid_image"] = render_crop_rulers(cropped, image_path, (px_x1, px_y1), img.size)
    if view.get("show_detail"):
        _add_detail(result, cropped, image_path, (px_x1, px_y1), proposed)
    return result


def _add_detail(
    result: CropResult, cropped: Image.Image, image_path: str, origin: Point, proposed: Box
) -> None:
    """Mark crop-local tips and report their half-open edges in original image coordinates."""
    x, y = origin
    left, top, right, bottom = proposed
    width, height = result["source_width"], result["source_height"]
    local = edge_checks(cropped, (left - x, top - y, right - x, bottom - y))
    result["edge_checks_px"] = {
        side: [(x + u, y + v) for u, v in points] for side, points in local.items()
    }
    result["traced_edges_px"] = {
        side: points[0][0 if side in ("left", "right") else 1] + int(side in ("right", "bottom"))
        for side, points in result["edge_checks_px"].items()
        if len(points) == 1
    }
    result["traced_edges_normalized"] = {
        side: value / (width if side in ("left", "right") else height)
        for side, value in result["traced_edges_px"].items()
    }
    result["detail_image"] = render_crop_rulers(
        cropped,
        image_path,
        origin,
        (width, height),
        proposed=proposed,
        checks=tuple(point for points in local.values() for point in points),
    )
