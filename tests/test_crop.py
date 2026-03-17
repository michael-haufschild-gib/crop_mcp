"""Tests for crop_image and image_info."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from PIL import Image

from tools.crop import crop_image, image_info


class TestCropImage:
    """Tests for crop_image."""

    def test_crop_left_half_is_red(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        assert result["width"] == 100
        assert result["height"] == 100
        cropped = Image.open(result["output_path"])
        # Center pixel of left half should be red
        assert cropped.getpixel((50, 50)) == (255, 0, 0)

    def test_crop_right_half_is_blue(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.5, 0.0, 1.0, 1.0, padding=0)
        assert result["width"] == 100
        assert result["height"] == 100
        cropped = Image.open(result["output_path"])
        assert cropped.getpixel((50, 50)) == (0, 0, 255)

    def test_padding_zero_exact_coords(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        assert result["crop_region_px"] == {"x1": 0, "y1": 0, "x2": 100, "y2": 100}

    def test_padding_applied_and_clamped(self, synthetic_image: Path) -> None:
        """Padding expands the crop but clamps to image bounds."""
        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=20)
        px = result["crop_region_px"]
        # Left/top should be clamped to 0 (can't go negative)
        assert px["x1"] == 0
        assert px["y1"] == 0
        # Right should expand by 20px
        assert px["x2"] == 120
        # Bottom should be clamped to image height
        assert px["y2"] == 100

    def test_full_image_crop(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.0, 0.0, 1.0, 1.0, padding=0)
        assert result["width"] == 200
        assert result["height"] == 100

    def test_negative_padding_raises(self, synthetic_image: Path) -> None:
        with pytest.raises(ValueError, match="padding must be >= 0"):
            crop_image(str(synthetic_image), 0.0, 0.0, 1.0, 1.0, padding=-5)

    def test_rgba_input_handled(self, tmp_path: Path) -> None:
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        path = tmp_path / "rgba.png"
        img.save(str(path))
        result = crop_image(str(path), 0.0, 0.0, 1.0, 1.0, padding=0)
        assert result["width"] == 100

    def test_palette_mode_handled(self, tmp_path: Path) -> None:
        img = Image.new("P", (100, 100))
        path = tmp_path / "palette.png"
        img.save(str(path))
        result = crop_image(str(path), 0.0, 0.0, 1.0, 1.0, padding=0)
        assert result["width"] == 100

    def test_custom_output_path(self, synthetic_image: Path, tmp_path: Path) -> None:
        out = tmp_path / "custom_crop.png"
        result = crop_image(
            str(synthetic_image),
            0.0,
            0.0,
            0.5,
            1.0,
            output_path=str(out),
            padding=0,
        )
        assert result["output_path"] == str(out)
        assert out.exists()

    def test_return_dict_has_all_keys(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        expected_keys = {
            "output_path",
            "width",
            "height",
            "source_width",
            "source_height",
            "crop_region_px",
            "crop_region_normalized",
        }
        assert set(result.keys()) == expected_keys

    def test_source_dimensions_returned(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        assert result["source_width"] == 200
        assert result["source_height"] == 100

    def test_output_is_valid_png(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        cropped = Image.open(result["output_path"])
        assert cropped.format == "PNG"
        assert cropped.size == (result["width"], result["height"])

    def test_normalized_region_returned(self, synthetic_image: Path) -> None:
        result = crop_image(str(synthetic_image), 0.25, 0.25, 0.75, 0.75, padding=0)
        norm = result["crop_region_normalized"]
        assert norm["x1"] == 0.25
        assert norm["y1"] == 0.25
        assert norm["x2"] == 0.75
        assert norm["y2"] == 0.75

    def test_corrupted_image_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not a PNG")
        with pytest.raises(ValueError, match="Could not open image"):
            crop_image(str(bad), 0.0, 0.0, 1.0, 1.0)


class TestImageInfo:
    """Tests for image_info."""

    def test_dimensions_correct(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        assert info["width"] == 200
        assert info["height"] == 100

    def test_aspect_ratio_landscape(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        assert info["aspect_ratio"] == 2.0

    def test_aspect_ratio_portrait(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        path = solid_color_image((0, 0, 0), (100, 200))
        info = image_info(str(path))
        assert info["aspect_ratio"] == 0.5

    def test_pixels_per_percent(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        # 200 * 0.01 = 2.0, 100 * 0.01 = 1.0
        assert info["pixels_per_percent"]["x"] == 2.0
        assert info["pixels_per_percent"]["y"] == 1.0

    def test_longer_axis_landscape(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        assert info["longer_axis"] == "x"

    def test_longer_axis_portrait(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        path = solid_color_image((0, 0, 0), (100, 200))
        info = image_info(str(path))
        assert info["longer_axis"] == "y"

    def test_grid_image_exists_and_valid(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        grid_path = Path(info["grid_image"])
        assert grid_path.exists()
        grid_img = Image.open(grid_path)
        assert grid_img.size == (200, 100)

    def test_file_size_positive(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        assert info["file_size_kb"] > 0

    def test_corrupted_image_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not a PNG")
        with pytest.raises(ValueError, match="Could not open image"):
            image_info(str(bad))

    def test_mode_field_present(self, synthetic_image: Path) -> None:
        info = image_info(str(synthetic_image))
        assert info["mode"] == "RGB"
