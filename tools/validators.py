"""Shared validators and utilities for vision-tools MCP server."""

from __future__ import annotations

import contextlib
from pathlib import Path

# Supported image extensions (lowercase)
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


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


def cleanup_temp_dir(dir_path: Path, max_mb: float = 50) -> None:
    """Evict oldest files if directory exceeds max_mb. Simple LRU by mtime.

    Args:
        dir_path: Directory to clean up.
        max_mb: Maximum size in megabytes before eviction starts.
    """
    if not dir_path.exists():
        return
    # Single stat() per file: cache both mtime and size
    entries: list[tuple[Path, float, int]] = []  # (path, mtime, size)
    for f in dir_path.iterdir():
        if f.is_file():
            st = f.stat()
            entries.append((f, st.st_mtime, st.st_size))
    entries.sort(key=lambda e: e[1])  # sort by mtime, oldest first
    total = sum(size for _, _, size in entries)
    limit = int(max_mb * 1024 * 1024)
    if total <= limit:
        return
    # Evict down to half the limit to avoid re-triggering on the next call
    target = limit // 2
    while total > target and entries:
        victim, _, size = entries.pop(0)
        total -= size
        with contextlib.suppress(OSError):
            victim.unlink(missing_ok=True)
