"""Locate small patches of color detail near a caller's proposed screenshot bounds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from numpy.typing import NDArray

type Point = tuple[int, int]
type Box = tuple[int, int, int, int]

# Five consecutive scan lines let us distinguish short structures from isolated outliers.
_TRACK_ROWS = 5
_SEARCH_MARGIN = 24
_MAX_NATIVE_VIEW = 1200
_MIN_RIDGE_CONTRAST = 4
_TIP_EDGE_TOLERANCE = 2
_TIP_LATERAL_TOLERANCE = 3


def _differences(img: Image.Image) -> tuple[NDArray[np.int16], NDArray[np.int16]]:
    # Premultiply first so invisible RGB cannot produce a visible edge next to transparency.
    pixels = np.asarray(img.convert("RGBa") if img.mode == "RGBA" else img, dtype=np.int16)
    color = pixels[:, :, (0, 2)] - pixels[:, :, 1:2]
    p = np.pad(color, ((1, 1), (1, 1), (0, 0)), mode="edge")
    horizontal = 2 * color - p[1:-1, :-2] - p[1:-1, 2:]
    vertical = 2 * color - p[:-2, 1:-1] - p[2:, 1:-1]
    return np.max(np.abs(horizontal), axis=2), np.max(np.abs(vertical), axis=2)


def detail_view(img: Image.Image) -> Image.Image:
    """Show fine color changes in cyan over the natural light/dark structure."""
    horizontal, vertical = _differences(img)
    gray = np.asarray(img.convert("L"), dtype=np.int16) // 2
    highlight = np.minimum(255, gray + 5 * (horizontal + vertical))
    view = Image.fromarray(np.stack((gray, highlight, highlight), axis=2).astype(np.uint8))
    if img.mode == "RGBA":
        view.putalpha(img.getchannel("A"))
    return view


def _crosses_edge(
    rgb: NDArray[np.int16], tracks: NDArray[np.int16], col: int, tip: int, edge: int, noise: float
) -> bool:
    """Check that a run continues through the proposal, using texture or two-sided contrast."""
    supported = tracks[tip : edge + 3, col] > noise
    radius = 3
    if radius <= col < rgb.shape[1] - radius:
        stripe = rgb[tip : edge + 3]
        center = stripe[:, col].astype(np.float32)
        left = center - stripe[:, col - radius]
        right = center - stripe[:, col + radius]
        # A narrow ridge differs in the same direction from BOTH flanks.
        # Use opponent colors plus attenuated brightness to tolerate shaded surroundings.
        a = np.column_stack(
            (left[:, 0] - left[:, 1], left[:, 2] - left[:, 1], left.mean(axis=1) / 4)
        )
        b = np.column_stack(
            (right[:, 0] - right[:, 1], right[:, 2] - right[:, 1], right.mean(axis=1) / 4)
        )
        la, lb = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
        supported |= (np.sum(a * b, axis=1) >= 0.5 * la * lb) & (
            np.minimum(la, lb) >= _MIN_RIDGE_CONTRAST
        )
    return bool(
        supported[0] and supported[-1] and np.count_nonzero(~supported) <= len(supported) // 6
    )


def _side_checks(
    band: NDArray[np.int16], rgb: NDArray[np.int16], edge: int, noise: float
) -> list[Point]:
    """Find the outward tips of sustained detail near one side; row count increases inward."""
    if edge < _TRACK_ROWS or not band.size:
        return []
    lo = max(0, edge - _SEARCH_MARGIN)
    # Allow a one-column drift either way as the feature crosses successive rows.
    padded = np.pad(band, ((0, 0), (1, 1)), mode="edge")
    tracks = np.maximum.reduce((padded[:, :-2], padded[:, 1:-1], padded[:, 2:]))
    windows = np.lib.stride_tricks.sliding_window_view(
        np.pad(tracks, ((2, 2), (0, 0)), mode="edge"), _TRACK_ROWS, axis=0
    )
    # Discard the largest value. A lone bright pixel cannot create a strong track.
    windows = windows[lo : edge + 2]
    scores = (windows.sum(axis=2) - windows.max(axis=2)) / (_TRACK_ROWS - 1)
    checks = []
    for _ in range(2):
        row, col = np.unravel_index(np.argmax(scores), scores.shape)
        if scores[row, col] <= noise:
            break
        tip = lo + int(row)
        while tip >= lo and tracks[tip, col] > noise:
            tip -= 1
        tip += 1
        if lo < tip < edge and tracks[lo + row, col] > noise:
            start = max(0, int(col) - 1)
            peak = start + int(np.argmax(band[tip, start : col + 2]))
            if _crosses_edge(rgb, tracks, peak, tip, edge, noise):
                checks.append((peak, tip))
        scores[:, max(0, int(col) - _TRACK_ROWS) : col + _TRACK_ROWS + 1] = 0
    return checks


def _scan(strength: NDArray[np.int16], rgb: NDArray[np.int16], box: Box) -> dict[str, list[Point]]:
    """Return crop-local pixel centers worth inspecting in the padding, grouped by side."""
    left, top, right, bottom = box
    # Estimate the noise level from the visible surround, outside the proposed rectangle.
    padding = np.ones(strength.shape, dtype=bool)
    padding[top:bottom, left:right] = False
    if not padding.any() or left >= right or top >= bottom:
        return {}
    noise = max(2.0, float(np.percentile(strength[padding], 98)))
    columns_rgb = rgb[:, left:right]
    rows_rgb = rgb[top:bottom].swapaxes(0, 1)
    cols = strength[:, left:right]
    rows = strength[top:bottom, :].T
    checks = {
        "top": [(left + x, y) for x, y in _side_checks(cols, columns_rgb, top, noise)],
        "bottom": [
            (left + x, strength.shape[0] - 1 - y)
            for x, y in _side_checks(
                cols[::-1], columns_rgb[::-1], strength.shape[0] - bottom, noise
            )
        ],
        "left": [(y, top + x) for x, y in _side_checks(rows, rows_rgb, left, noise)],
        "right": [
            (strength.shape[1] - 1 - y, top + x)
            for x, y in _side_checks(rows[::-1], rows_rgb[::-1], strength.shape[1] - right, noise)
        ],
    }
    return {side: points for side, points in checks.items() if points}


def _neighbors(p: Point, q: Point, axis: int) -> bool:
    return (
        abs(p[axis] - q[axis]) <= _TIP_EDGE_TOLERANCE
        and abs(p[1 - axis] - q[1 - axis]) <= _TIP_LATERAL_TOLERANCE
    )


def _nearest_tip(measurement: list[Point], point: Point, axis: int) -> Point | None:
    return min(
        (q for q in measurement if _neighbors(q, point, axis)),
        key=lambda q: abs(q[0] - point[0]) + abs(q[1] - point[1]),
        default=None,
    )


def _repeatable(scans: list[list[Point]], side: str) -> list[Point]:
    """Locate tips supported by separate proposals; leave competing features distinct."""
    axis = 0 if side in ("left", "right") else 1
    tips: list[Point] = []
    for scan in scans:
        for point in scan:
            if any(_neighbors(point, other, axis) for other in tips):
                continue
            votes = [
                vote
                for measurement in scans
                if (vote := _nearest_tip(measurement, point, axis)) is not None
            ]
            if len(votes) > len(scans) // 2:
                tips.append(sorted(votes, key=lambda q: q[axis])[len(votes) // 2])
    return tips


def edge_checks(img: Image.Image, box: Box) -> dict[str, list[Point]]:
    """Accept a tip only when shifting the proposed boundary still locates it."""
    if max(img.size) > _MAX_NATIVE_VIEW:
        return {}
    horizontal, vertical = _differences(img)
    strength = np.minimum(horizontal, vertical)
    rgb = np.asarray(img.convert("RGBa") if img.mode == "RGBA" else img, dtype=np.int16)[:, :, :3]
    left, top, right, bottom = box
    scans = []
    for shift in (-3, 0, 3):
        shifted = (
            max(0, left + shift),
            max(0, top + shift),
            min(img.width, right - shift),
            min(img.height, bottom - shift),
        )
        scans.append(_scan(strength, rgb, shifted))
    return {
        side: pts
        for side in ("left", "top", "right", "bottom")
        if (pts := _repeatable([s.get(side, []) for s in scans], side))
    }
