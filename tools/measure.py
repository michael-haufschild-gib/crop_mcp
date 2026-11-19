"""Measure the four-connected, identical-color fill under a screenshot point."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypedDict

from PIL import Image, ImageChops, ImageDraw

from .validators import pixel_edge

if TYPE_CHECKING:
    from collections.abc import Sequence

_FILLED = 128
_POINT_DIMENSIONS = 2


class FillBounds(TypedDict):
    hex: str
    bounds_px: list[int]
    bounds_normalized: list[float]
    width: int
    height: int


def measure_fill(image: Image.Image, point: Sequence[float]) -> FillBounds:
    """Return half-open bounds in source coordinates. Internal lettering can form holes."""
    if len(point) != _POINT_DIMENSIONS or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1
        for v in point
    ):
        raise ValueError("measure_at must be [x, y] with normalized coordinates between 0 and 1.")
    x = min(image.width - 1, pixel_edge(point[0], image.width))
    y = min(image.height - 1, pixel_edge(point[1], image.height))
    src = image.convert("RGBA")
    color = src.getpixel((x, y))
    assert isinstance(color, tuple)
    # Channel-wise equality includes alpha. The mask distinguishes this component
    # from disconnected regions with the same fill and other colors with equal luminance.
    diff = ImageChops.difference(src, Image.new("RGBA", src.size, color))
    red, green, blue, alpha = diff.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), ImageChops.lighter(blue, alpha))
    mask = mask.point([0] + [255] * 255)
    ImageDraw.floodfill(mask, (x, y), _FILLED)
    bounds = mask.point([255 if n == _FILLED else 0 for n in range(256)]).getbbox()
    assert bounds is not None
    left, top, right, bottom = bounds
    return {
        "hex": f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}",
        "bounds_px": list(bounds),
        "bounds_normalized": [
            left / image.width,
            top / image.height,
            right / image.width,
            bottom / image.height,
        ],
        "width": right - left,
        "height": bottom - top,
    }
