"""Coordinate rulers for whole screenshots and magnified source regions."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from .runtime import save_png

if TYPE_CHECKING:
    from .edge_detail import Box, Point

_GRID_MAX_DIM = 4000
_CROP_VIEW_DIM = 1200
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
YELLOW = (200, 200, 0)
_PREVIEW_EDGE = 1400


def _draw_axis(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    *,
    horizontal: bool,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    length, depth = size if horizontal else size[::-1]
    for index in range(1, 20):
        value = index / 20
        pos = round(value * length)
        major = index % 2 == 0
        color = (YELLOW if math.isclose(value, 0.5) else CYAN) if major else MAGENTA
        line = (pos, 0, pos, depth - 1) if horizontal else (0, pos, depth - 1, pos)
        draw.line(
            line,
            fill=(*color, 152 if major else 95),
            width=max(1, round(max(size) / _PREVIEW_EDGE)),
        )
        if major:
            label = f"{value:.8f}".rstrip("0").rstrip(".").lstrip("0")
            left, top, right, bottom = font.getbbox(label)
            label_space = (right - left if horizontal else bottom - top) + 6
            stride = max(1, math.ceil(label_space / (length / 10)))
            if index // 2 % stride == 0:
                _label(draw, size, pos, horizontal, label, font, color)


def _label(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    pos: int,
    horizontal: bool,
    label: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    color: tuple[int, int, int],
) -> None:
    left, top, right, bottom = font.getbbox(label)
    width, height = math.ceil(right - left) + 4, math.ceil(bottom - top) + 4
    w, h = size
    if horizontal:
        x = max(0, min(pos - width // 2, w - width))
        positions = ((x, 0), (x, h - height))
    else:
        y = max(0, min(pos - height // 2, h - height))
        positions = ((0, y), (w - width, y))
    for x, y in positions:
        draw.rectangle((x, y, x + width - 1, y + height - 1), fill=(0, 0, 0, 210))
        draw.text((x + 2 - left, y + 2 - top), label, font=font, fill=(*color, 255))


def render_grid(img: Image.Image, source_path: str) -> str:
    """Draw a normalized coordinate grid on a complete screenshot."""
    del source_path  # Retained for callers of the original rendering API.
    view = img
    if max(img.size) > _GRID_MAX_DIM:
        scale = _GRID_MAX_DIM / max(img.size)
        size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        view = img.resize(size, Image.Resampling.LANCZOS, reducing_gap=2)

    overlay = Image.new("RGBA", view.size)
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=max(12, min(33, round(max(view.size) / 80))))
    _draw_axis(draw, view.size, horizontal=True, font=font)
    _draw_axis(draw, view.size, horizontal=False, font=font)
    base = view if view.mode == "RGBA" else view.convert("RGBA")
    return str(save_png(Image.alpha_composite(base, overlay), "grid"))


_RULER_X = 70
_RULER_Y = 30


def _interval(minimum: float) -> int:
    unit = int(10 ** max(0, math.floor(math.log10(minimum))))
    return next(unit * n for n in (1, 2, 5, 10) if unit * n >= minimum)


def _crop_axis(
    draw: ImageDraw.ImageDraw,
    view: Image.Image,
    horizontal: bool,
    start: int,
    span: int,
    original_length: int,
) -> None:
    length = view.width if horizontal else view.height
    scale = length / span
    major = _interval(66 / scale)
    minor = _interval(4 / scale)
    font = ImageFont.load_default(size=14)
    for edge in range(math.ceil(start / minor) * minor, start + span + 1, minor):
        offset = round((edge - start) * scale)
        labeled = edge % major == 0
        tick = 7 if labeled else 3
        shade = "#efefef" if labeled else "#a8b5bd"
        frac = f"{edge / original_length:.5f}".rstrip("0").rstrip(".")
        if horizontal:
            x, y = _RULER_X + offset, _RULER_Y + view.height
            draw.line((x, _RULER_Y - tick, x, _RULER_Y - 1), fill=shade)
            draw.line((x, y, x, y + tick - 1), fill=shade)
            if labeled:
                draw.text((x, _RULER_Y - 10), str(edge), font=font, fill=shade, anchor="ms")
                draw.text((x, y + 10), frac, font=font, fill=CYAN, anchor="mt")
        else:
            x, y = _RULER_X + view.width, _RULER_Y + offset
            draw.line((_RULER_X - tick, y, _RULER_X - 1, y), fill=shade)
            draw.line((x, y, x + tick - 1, y), fill=shade)
            if labeled:
                draw.text((_RULER_X - 10, y), str(edge), font=font, fill=shade, anchor="rm")
                draw.text((x + 10, y), frac, font=font, fill=CYAN, anchor="lm")


def render_crop_rulers(
    img: Image.Image,
    source_path: str,
    origin: tuple[int, int],
    source_size: tuple[int, int],
    *,
    proposed: Box | None = None,
    checks: tuple[Point, ...] = (),
) -> str:
    """Keep source pixels visible between pixel rulers and normalized rulers."""
    del source_path
    fit = _CROP_VIEW_DIM / max(img.size)
    scale = min(8, math.floor(fit)) if fit >= 1 else fit
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    base = img if scale >= 1 else img.resize(size, Image.Resampling.LANCZOS)
    if proposed is not None:
        from .edge_detail import detail_view

        base = detail_view(base)
    view = base.resize(size, Image.Resampling.NEAREST) if scale > 1 else base
    canvas = Image.new("RGBA", (view.width + 2 * _RULER_X, view.height + 2 * _RULER_Y), "#192026")
    draw = ImageDraw.Draw(canvas)
    _crop_axis(draw, view, True, origin[0], img.width, source_size[0])
    _crop_axis(draw, view, False, origin[1], img.height, source_size[1])
    canvas.paste(view, (_RULER_X, _RULER_Y))
    if proposed is not None:
        x1, y1, x2, y2 = proposed
        x = [_RULER_X + round((edge - origin[0]) * view.width / img.width) for edge in (x1, x2)]
        y = [_RULER_Y + round((edge - origin[1]) * view.height / img.height) for edge in (y1, y2)]
        # A stroke in the padding leaves even the first and last target pixels visible.
        draw.rectangle((x[0] - 1, y[0] - 1, x[1], y[1]), outline="#ff408f")
        for px, py in checks:
            cx = _RULER_X + (px + 0.5) * view.width / img.width
            cy = _RULER_Y + (py + 0.5) * view.height / img.height
            radius = max(4, 2 * scale)
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline="#ffd850")
    return str(save_png(canvas, "detail" if proposed is not None else "grid"))
