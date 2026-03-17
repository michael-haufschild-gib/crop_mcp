"""extract_colors tool — Extract dominant colors from an image using numpy k-means."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from .validators import validate_coordinates, validate_image_path

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

    Performance:
        Memory is O(N * k * 3) float64 for the distance matrix each iteration
        plus O(N * 3) float64 for the pre-converted pixel array.
        At MAX_ANALYSIS_DIM=200 (40K pixels) and MAX_COLORS=20: ~18 MB per iteration.
        Callers must thumbnail images to MAX_ANALYSIS_DIM before calling this function.
    """
    n = pixels.shape[0]

    # Convert once — avoid repeated astype(float64) in hot loops
    pixels_f: np.ndarray = pixels.astype(np.float64)

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
    centers[0] = pixels_f[rng.integers(n)]

    for i in range(1, k):
        # Distance from each point to nearest existing center
        dists = np.min(
            np.sum((pixels_f[:, None, :] - centers[None, :i, :]) ** 2, axis=2),
            axis=1,
        )
        # Probability proportional to distance squared
        total_dist = dists.sum()
        if total_dist == 0:
            idx = rng.integers(n)
        else:
            probs = dists / total_dist
            idx = rng.choice(n, p=probs)
        centers[i] = pixels_f[idx]

    # Iterate
    for _ in range(max_iter):
        # Assign each pixel to nearest center
        dists = np.sum((pixels_f[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(dists, axis=1)

        # Update centers
        new_centers = np.empty_like(centers)
        for i in range(k):
            members = pixels_f[labels == i]
            if len(members) > 0:
                new_centers[i] = members.mean(axis=0)
            else:
                # Empty cluster — reinitialize randomly
                new_centers[i] = pixels_f[rng.integers(n)]

        # Check convergence
        if np.allclose(centers, new_centers, atol=1.0):
            centers = new_centers
            break
        centers = new_centers

    # Recompute labels against final centers so they're consistent
    dists = np.sum((pixels_f[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    labels = np.argmin(dists, axis=1)

    return centers, labels


def _validate_region(
    x1: float | None,
    y1: float | None,
    x2: float | None,
    y2: float | None,
) -> tuple[float, float, float, float] | None:
    """Validate optional region coordinates.

    Returns:
        The four coordinates as a tuple if all are provided, or None if all are omitted.

    Raises:
        ValueError: If coordinates are partially provided or out of range.
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

    if all_provided and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
        validate_coordinates(x1, y1, x2, y2)
        return (x1, y1, x2, y2)

    return None


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
) -> list[dict[str, Any]]:
    """Convert k-means centers and labels to sorted color result list."""
    total = len(labels)
    results: list[dict[str, Any]] = []
    for i, center in enumerate(centers):
        count = int(np.sum(labels == i))
        if count == 0:
            continue
        r = max(0, min(255, round(float(center[0]))))
        g = max(0, min(255, round(float(center[1]))))
        b = max(0, min(255, round(float(center[2]))))
        results.append(
            {
                "hex": f"#{r:02X}{g:02X}{b:02X}",
                "percentage": round(count / total * 100, 1),
                "rgb": [r, g, b],
            }
        )
    results.sort(key=lambda c: float(c["percentage"]), reverse=True)
    return results


def extract_colors(
    image_path: str,
    n_colors: int = 6,
    x1: float | None = None,
    y1: float | None = None,
    x2: float | None = None,
    y2: float | None = None,
) -> dict[str, Any]:
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

    region = _validate_region(x1, y1, x2, y2)

    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(f"Could not open image: {path}\nError: {e}") from e

    img = img.convert("RGB")
    full_size = img.size

    if region is not None:
        img, region_str = _crop_to_region(img, *region)
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
