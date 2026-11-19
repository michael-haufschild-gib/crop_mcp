"""Shared validators and utilities for vision-tools MCP server."""

from __future__ import annotations

import math
from contextlib import contextmanager
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageOps

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "open_image",
    "pixel_edge",
    "read_image",
    "validate_coordinates",
    "validate_image_path",
]

# Supported image extensions (lowercase)
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def pixel_edge(fraction: float, dimension: int) -> int:
    """Floor a normalized edge, preserving integer edges on a float round trip."""
    scaled = fraction * dimension
    nearest = round(scaled)
    return nearest if abs(scaled - nearest) <= math.ulp(scaled) else int(scaled)


_MAX_PIXELS = 24_000_000


@contextmanager
def open_image(path: Path) -> Iterator[Image.Image]:
    """Check the pixel budget before decoding. The caller owns the image inside the context."""
    try:
        opened = Image.open(path)
        try:
            if opened.width * opened.height > _MAX_PIXELS:
                raise ValueError(f"Image exceeds the {_MAX_PIXELS:,}-pixel limit. Resize it first.")
            ImageOps.exif_transpose(opened, in_place=True)
        except BaseException:
            opened.close()
            raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError(f"Could not open image: {path}\nError: {exc}") from exc
    try:
        yield opened
    finally:
        opened.close()


def read_image(path: Path) -> Image.Image:
    """Return an independent, display-oriented image for callers that retain it."""
    with open_image(path) as source:
        return source.copy()


def validate_image_path(image_path: str) -> Path:
    """Validate that the image path exists and is a readable image file.

    Args:
        image_path: Absolute or relative path to an image file.

    Returns:
        The resolved Path on success.

    Raises:
        ValueError: If the file does not exist, is not a file, or has an
            unsupported extension. The error message includes suggestions.
    """
    path = Path(image_path).expanduser().resolve()

    if not path.exists():
        parent = path.parent
        if not parent.exists():
            raise ValueError(
                f"Image not found: {image_path}\n"
                f"The directory '{parent}' does not exist either.\n"
                f"Hint: Use an absolute path like /Users/you/screenshots/image.png"
            )
        names = (f.name for f in parent.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
        similar = list(islice(names, 5))
        if similar:
            suggestions = ", ".join(similar)
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

    Args:
        x1: Left edge (0.0 = left).
        y1: Top edge (0.0 = top).
        x2: Right edge (1.0 = right).
        y2: Bottom edge (1.0 = bottom).

    Raises:
        ValueError: If any coordinate is out of range, non-numeric, or
            improperly ordered. The error message explains the coordinate system.
    """
    coords = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    for name, val in coords.items():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(
                f"'{name}' must be a finite number, got {type(val).__name__}.\n"
                f"Coordinates use a 0-1 scale: 0.0 = left/top edge, 1.0 = right/bottom edge."
            )
        if not math.isfinite(float(val)):
            raise ValueError(
                f"'{name}' must be finite, got {val}.\n"
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
