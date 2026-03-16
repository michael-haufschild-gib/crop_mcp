"""crop_image tool — Crop a region from an image using normalized 0-1 coordinates."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

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
                f"Image not found: {image_path}\n"
                f"Images in that directory: {suggestions}"
            )
        raise ValueError(
            f"Image not found: {image_path}\n"
            f"Hint: Make sure you're using the full absolute path."
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
        )

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
    }
