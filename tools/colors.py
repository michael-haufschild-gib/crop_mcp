"""extract_colors tool — Extract dominant colors from an image using numpy k-means."""

from __future__ import annotations

import numpy as np
from PIL import Image

from .crop import SUPPORTED_EXTENSIONS, validate_image_path, validate_coordinates

# Maximum dimension for color analysis (larger images are downsampled)
MAX_ANALYSIS_DIM = 200


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
        dists = np.sum(
            (pixels[:, None, :].astype(np.float64) - centers[None, :, :]) ** 2, axis=2
        )
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

    # Validate n_colors
    if not isinstance(n_colors, int) or n_colors < 1:
        raise ValueError(
            f"n_colors must be a positive integer, got {n_colors}.\n"
            f"Typical values: 3-10. Default is 6."
        )
    if n_colors > 20:
        raise ValueError(
            f"n_colors = {n_colors} is too high. Maximum is 20.\n"
            f"Most images have 3-8 dominant colors. Try n_colors=6."
        )

    # Validate region coordinates if any are provided
    region_coords = [x1, y1, x2, y2]
    some_provided = any(c is not None for c in region_coords)
    all_provided = all(c is not None for c in region_coords)

    if some_provided and not all_provided:
        missing = []
        for name, val in [("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2)]:
            if val is None:
                missing.append(name)
        raise ValueError(
            f"Incomplete region: {', '.join(missing)} not provided.\n"
            f"Either provide all four coordinates (x1, y1, x2, y2) to analyze a region,\n"
            f"or omit all four to analyze the full image."
        )

    if all_provided:
        validate_coordinates(x1, y1, x2, y2)

    # Open image
    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(f"Could not open image: {path}\nError: {e}")

    # Convert to RGB (drop alpha, handle palette images)
    img = img.convert("RGB")
    full_size = img.size  # (width, height)

    # Crop to region if specified
    if all_provided:
        w, h = img.size
        px_x1 = int(x1 * w)
        px_y1 = int(y1 * h)
        px_x2 = int(x2 * w)
        px_y2 = int(y2 * h)
        img = img.crop((px_x1, px_y1, px_x2, px_y2))
        region_str = f"({x1:.2f}, {y1:.2f}) to ({x2:.2f}, {y2:.2f})"
    else:
        region_str = "full image"

    # Ensure we have pixels to work with
    if img.size[0] < 1 or img.size[1] < 1:
        raise ValueError(
            f"Region is too small ({img.size[0]}x{img.size[1]} pixels).\n"
            f"Try a larger region or the full image."
        )

    # Downsample for performance (color clustering doesn't need full resolution)
    if img.size[0] > MAX_ANALYSIS_DIM or img.size[1] > MAX_ANALYSIS_DIM:
        img.thumbnail((MAX_ANALYSIS_DIM, MAX_ANALYSIS_DIM), Image.LANCZOS)

    # Convert to numpy array and reshape to (N, 3)
    pixels = np.array(img).reshape(-1, 3)

    # Run k-means
    centers, labels = _kmeans(pixels, n_colors)

    # Count pixels per cluster and compute percentages
    total = len(labels)
    results = []
    for i in range(len(centers)):
        count = int(np.sum(labels == i))
        if count == 0:
            continue
        r, g, b = int(round(centers[i][0])), int(round(centers[i][1])), int(round(centers[i][2]))
        # Clamp to valid range
        r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
        hex_val = f"#{r:02X}{g:02X}{b:02X}"
        percentage = round(count / total * 100, 1)
        results.append({
            "hex": hex_val,
            "percentage": percentage,
            "rgb": [r, g, b],
        })

    # Sort by percentage descending
    results.sort(key=lambda c: c["percentage"], reverse=True)

    return {
        "colors": results,
        "image_size": list(full_size),
        "region_analyzed": region_str,
    }
