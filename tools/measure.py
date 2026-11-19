"""Measure the four-connected, identical-color fill under a screenshot point."""

from __future__ import annotations

import math
import re
from array import array
from typing import TYPE_CHECKING, TypedDict

from PIL import ImageChops

from .runtime import check_active
from .validators import pixel_edge

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PIL import Image

_RUN = re.compile(b"\xff+")
_POINT_DIMENSIONS = 2
_RUNS_PER_CANCEL_CHECK = 1024


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
    src = (
        image
        if image.mode in ("RGB", "RGBA") and "transparency" not in image.info
        else image.convert("RGBA")
    )
    color = src.getpixel((x, y))
    if not isinstance(color, tuple):
        raise RuntimeError("Expected a color pixel after image conversion.")
    mask = _matching_pixels(src, color)
    left, top, right, bottom = _component_bounds(mask, x, y, src.width)
    return {
        "hex": f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}",
        "bounds_px": [left, top, right, bottom],
        "bounds_normalized": [
            left / image.width,
            top / image.height,
            right / image.width,
            bottom / image.height,
        ],
        "width": right - left,
        "height": bottom - top,
    }


def _matching_pixels(image: Image.Image, color: tuple[int, ...]) -> bytearray:
    """One byte per pixel. Compare alpha too, even for fully transparent pixels."""
    mask = None
    for band, value in zip(image.getbands(), color, strict=True):
        lookup = [0] * 256
        lookup[value] = 255
        matches = image.getchannel(band).point(lookup)
        mask = matches if mask is None else ImageChops.darker(mask, matches)
    if mask is None:
        raise RuntimeError("Cannot measure an image without bands.")
    return bytearray(mask.tobytes())


def _component_bounds(mask: bytearray, x: int, y: int, width: int) -> tuple[int, int, int, int]:
    """Visit horizontal runs; only overlap on an adjacent row connects two runs."""
    pending = array("I", [y * width + x])
    left, top, right, bottom = x, y, x + 1, y + 1
    runs = 0
    while pending:
        if runs % _RUNS_PER_CANCEL_CHECK == 0:
            check_active()
        runs += 1
        point = pending.pop()
        if not mask[point]:
            continue
        row = point // width
        start = row * width
        lo = mask.rfind(0, start, point)
        lo = start if lo == -1 else lo + 1
        hi = mask.find(0, point, start + width)
        hi = start + width if hi == -1 else hi
        mask[lo:hi] = bytes(hi - lo)
        left, right = min(left, lo - start), max(right, hi - start)
        top, bottom = min(top, row), max(bottom, row + 1)
        for offset in (-width, width):
            if 0 <= lo + offset < len(mask):
                pending.extend(m.start() for m in _RUN.finditer(mask, lo + offset, hi + offset))
    return left, top, right, bottom
