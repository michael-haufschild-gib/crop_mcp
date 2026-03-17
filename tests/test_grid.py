"""Pixel-level tests for grid rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
from unittest.mock import patch

from PIL import Image

from tools.grid import CYAN, YELLOW, render_grid


def _color_distance(c1: tuple[int, ...], c2: tuple[int, int, int]) -> float:
    """Euclidean distance between two RGB colors (ignoring alpha)."""
    return float(sum((a - b) ** 2 for a, b in zip(c1[:3], c2)) ** 0.5)


class TestGridRendering:
    """Tests for render_grid."""

    def test_output_dimensions_match_source(self, synthetic_image: Path) -> None:
        img = Image.open(synthetic_image)
        grid_path = render_grid(img, str(synthetic_image))
        grid_img = Image.open(grid_path)
        assert grid_img.size == img.size

    def test_midpoint_gridline_is_yellow(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """The .5 vertical gridline should have yellow-ish pixels."""
        path = solid_color_image((128, 128, 128), (400, 400))
        img = Image.open(path)
        grid_path = render_grid(img, str(path))
        grid_img = Image.open(grid_path)
        # Sample pixel at the .5 gridline, middle of image
        x = int(0.5 * 400)
        y = 400 // 2
        pixel = grid_img.getpixel((x, y))
        # Should be closer to yellow than to cyan or magenta
        dist_yellow = _color_distance(pixel, YELLOW)
        dist_cyan = _color_distance(pixel, CYAN)
        assert dist_yellow < dist_cyan, f"Midpoint pixel {pixel} not yellow-ish"

    def test_non_midpoint_gridline_is_cyan(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """The .1 vertical gridline should have cyan-ish pixels."""
        path = solid_color_image((128, 128, 128), (400, 400))
        img = Image.open(path)
        grid_path = render_grid(img, str(path))
        grid_img = Image.open(grid_path)
        x = int(0.1 * 400)
        # Use y=28 (0.07) to avoid crossing any horizontal gridline
        y = int(0.07 * 400)
        pixel = grid_img.getpixel((x, y))
        dist_cyan = _color_distance(pixel, CYAN)
        dist_yellow = _color_distance(pixel, YELLOW)
        assert dist_cyan < dist_yellow, f"Non-midpoint pixel {pixel} not cyan-ish"

    def test_minor_gridline_is_magenta(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """The 5% gridline should have magenta-ish pixels."""
        path = solid_color_image((128, 128, 128), (400, 400))
        img = Image.open(path)
        grid_path = render_grid(img, str(path))
        grid_img = Image.open(grid_path)
        x = int(0.05 * 400)
        # Use y=28 (0.07) to avoid crossing any horizontal gridline
        y = int(0.07 * 400)
        pixel = grid_img.getpixel((x, y))
        # Background is gray; magenta overlay should shift R and B channels up
        # relative to a non-gridline pixel
        bg_pixel = grid_img.getpixel((int(0.07 * 400), y))
        assert pixel[0] > bg_pixel[0] or pixel[2] > bg_pixel[2], (
            f"Minor gridline pixel {pixel} shows no magenta shift vs background {bg_pixel}"
        )

    def test_font_fallback_does_not_crash(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """When no system fonts exist, _get_font falls back to default."""
        path = solid_color_image((128, 128, 128), (200, 200))
        img = Image.open(path)
        with patch("tools.grid._FONT_PATHS", ["/nonexistent/font.ttf"]):
            grid_path = render_grid(img, str(path))
            assert Path(grid_path).exists()

    def test_deterministic_output(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """Two calls with same input produce identical pixel data."""
        path = solid_color_image((128, 128, 128), (200, 200))
        img = Image.open(path)
        grid1 = Image.open(render_grid(img, str(path)))
        grid2 = Image.open(render_grid(img, str(path)))
        assert grid1.tobytes() == grid2.tobytes()

    def test_small_image_does_not_crash(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """Grid rendering on a very small image (10x10) should not crash."""
        path = solid_color_image((128, 128, 128), (10, 10))
        img = Image.open(path)
        grid_path = render_grid(img, str(path))
        grid_img = Image.open(grid_path)
        assert grid_img.size == (10, 10)

    def test_output_is_valid_rgba_png(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        """Grid output should be a valid RGBA PNG."""
        path = solid_color_image((128, 128, 128), (200, 200))
        img = Image.open(path)
        grid_path = render_grid(img, str(path))
        grid_img = Image.open(grid_path)
        assert grid_img.mode == "RGBA"
        assert grid_img.format == "PNG"
