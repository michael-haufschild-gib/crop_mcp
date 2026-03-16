"""extract_colors tool — Extract dominant colors from an image using numpy k-means."""

from __future__ import annotations

import numpy as np
from PIL import Image

from .crop import validate_coordinates, validate_image_path

# Maximum dimension for color analysis (larger images are downsampled)
MAX_ANALYSIS_DIM = 200
MIN_COLORS = 1
MAX_COLORS = 20


def _kmeans(pixels: np.ndarray, k: int, max_iter: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """Simple k-means clustering for RGB pixels. No scipy/sklearn needed.

    Args:
        pixels: (N, 3) array of RGB values.
        k: Number of clusters.
        max_iter: Maximum iterations.

    Returns:
        (centers, labels) — cluster centers (k, 3) and per-pixel labels (N,).
    """
    n = pixels.shape[0]

    # Clamp k to available unique colors
    unique_colors = np.unique(pixels, axis=0)
    if len(unique_colors) <= k:
        # Fewer unique colors than requested clusters — just return the unique colors
        centers = unique_colors.astype(np.float64)
        # Assign each pixel to its exact color
        labels = np.zeros(n, dtype=np.int32)
        for i, c in enumerate(centers):
            mask = np.all(pixels == c.astype(pixels.dtype), axis=1)
            labels[mask] = i
        return centers, labels

    # Initialize centers using k-means++ for better convergence
    rng = np.random.default_rng(42)
    centers = np.empty((k, 3), dtype=np.float64)
    centers[0] = pixels[rng.integers(n)].astype(np.float64)

    for i in range(1, k):
        # Distance from each point to nearest existing center
        dists = np.min(
            np.sum((pixels[:, None, :].astype(np.float64) - centers[None, :i, :]) ** 2, axis=2),
            axis=1,
        )
        # Probability proportional to distance squared
        probs = dists / dists.sum()
        idx = rng.choice(n, p=probs)
        centers[i] = pixels[idx].astype(np.float64)

    # Iterate
    for _ in range(max_iter):
        # Assign each pixel to nearest center
        dists = np.sum((pixels[:, None, :].astype(np.float64) - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(dists, axis=1)

        # Update centers
        new_centers = np.empty_like(centers)
        for i in range(k):
            members = pixels[labels == i]
            if len(members) > 0:
                new_centers[i] = members.mean(axis=0)
            else:
                # Empty cluster — reinitialize randomly
                new_centers[i] = pixels[rng.integers(n)].astype(np.float64)

        # Check convergence
        if np.allclose(centers, new_centers, atol=1.0):
            centers = new_centers
            break
        centers = new_centers

    return centers, labels


def _validate_region(
    x1: float | None,
    y1: float | None,
    x2: float | None,
    y2: float | None,
) -> bool:
    """Validate optional region coordinates. Returns True if region is specified.

    Raises ValueError if coordinates are partially provided.
    """
    region_coords = [x1, y1, x2, y2]
    some_provided = any(c is not None for c in region_coords)
    all_provided = all(c is not None for c in region_coords)

    if some_provided and not all_provided:
        missing = [
            name for name, val in [("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2)] if val is None
        ]
        raise ValueError(
            f"Incomplete region: {', '.join(missing)} not provided.\n"
            f"Either provide all four coordinates (x1, y1, x2, y2) to analyze a region,\n"
            f"or omit all four to analyze the full image."
        )

    if all_provided:
        validate_coordinates(x1, y1, x2, y2)

    return all_provided


def _crop_to_region(
    img: Image.Image,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[Image.Image, str]:
    """Crop image to normalized region. Returns (cropped_image, region_description)."""
    w, h = img.size
    cropped = img.crop((int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)))
    return cropped, f"({x1:.2f}, {y1:.2f}) to ({x2:.2f}, {y2:.2f})"


def _centers_to_color_list(
    centers: np.ndarray,
    labels: np.ndarray,
) -> list[dict]:
    """Convert k-means centers and labels to sorted color result list."""
    total = len(labels)
    results = []
    for i in range(len(centers)):
        count = int(np.sum(labels == i))
        if count == 0:
            continue
        r = max(0, min(255, round(centers[i][0])))
        g = max(0, min(255, round(centers[i][1])))
        b = max(0, min(255, round(centers[i][2])))
        results.append(
            {
                "hex": f"#{r:02X}{g:02X}{b:02X}",
                "percentage": round(count / total * 100, 1),
                "rgb": [r, g, b],
            }
        )
    results.sort(key=lambda c: c["percentage"], reverse=True)
    return results


def extract_colors(
    image_path: str,
    n_colors: int = 6,
    x1: float | None = None,
    y1: float | None = None,
    x2: float | None = None,
    y2: float | None = None,
) -> dict:
    """Extract dominant colors from an image or image region.

    Args:
        image_path: Absolute path to the source image.
        n_colors: Number of dominant colors to extract (default 6).
        x1, y1, x2, y2: Optional region (normalized 0-1). Omit all four for full image.

    Returns:
        Dict with colors (hex, percentage, rgb), image_size, region_analyzed.
    """
    path = validate_image_path(image_path)

    if not isinstance(n_colors, int) or n_colors < MIN_COLORS:
        raise ValueError(
            f"n_colors must be a positive integer, got {n_colors}.\n"
            f"Typical values: 3-10. Default is 6."
        )
    if n_colors > MAX_COLORS:
        raise ValueError(
            f"n_colors = {n_colors} is too high. Maximum is {MAX_COLORS}.\n"
            f"Most images have 3-8 dominant colors. Try n_colors=6."
        )

    has_region = _validate_region(x1, y1, x2, y2)

    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(f"Could not open image: {path}\nError: {e}") from e

    img = img.convert("RGB")
    full_size = img.size

    if has_region:
        img, region_str = _crop_to_region(img, x1, y1, x2, y2)
    else:
        region_str = "full image"

    if img.size[0] < 1 or img.size[1] < 1:
        raise ValueError(
            f"Region is too small ({img.size[0]}x{img.size[1]} pixels).\n"
            f"Try a larger region or the full image."
        )

    if img.size[0] > MAX_ANALYSIS_DIM or img.size[1] > MAX_ANALYSIS_DIM:
        img.thumbnail((MAX_ANALYSIS_DIM, MAX_ANALYSIS_DIM), Image.LANCZOS)

    pixels = np.array(img).reshape(-1, 3)
    centers, labels = _kmeans(pixels, n_colors)

    return {
        "colors": _centers_to_color_list(centers, labels),
        "image_size": list(full_size),
        "region_analyzed": region_str,
    }
