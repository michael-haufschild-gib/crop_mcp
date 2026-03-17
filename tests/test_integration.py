"""End-to-end integration tests exercising the full tool pipeline."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from tools.colors import extract_colors
from tools.crop import crop_image, image_info


class TestFullPipeline:
    """Round-trip tests: image → info → crop → colors."""

    def test_info_then_crop_then_colors(self, synthetic_image: Path) -> None:
        """Full pipeline: get info, crop the left half, extract its color."""
        # Step 1: Get image info
        info = image_info(str(synthetic_image))
        assert info["width"] == 200
        assert info["height"] == 100
        assert Path(info["grid_image"]).exists()

        # Step 2: Crop the left half (should be pure red)
        crop_result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        assert crop_result["width"] == 100
        assert crop_result["height"] == 100
        assert Path(crop_result["output_path"]).exists()

        # Step 3: Extract colors from the cropped region
        color_result = extract_colors(crop_result["output_path"], n_colors=1)
        assert color_result["colors"][0]["hex"] == "#FF0000"
        assert color_result["colors"][0]["percentage"] == 100.0

    def test_info_then_crop_right_half_then_colors(self, synthetic_image: Path) -> None:
        """Crop the right half (blue) and verify color extraction."""
        crop_result = crop_image(str(synthetic_image), 0.5, 0.0, 1.0, 1.0, padding=0)
        color_result = extract_colors(crop_result["output_path"], n_colors=1)
        assert color_result["colors"][0]["hex"] == "#0000FF"

    def test_color_region_matches_crop(self, synthetic_image: Path) -> None:
        """Extracting colors from a region should match cropping then extracting."""
        # Method 1: Extract colors from left half region directly
        direct_result = extract_colors(
            str(synthetic_image), n_colors=1, x1=0.0, y1=0.0, x2=0.5, y2=1.0
        )

        # Method 2: Crop left half, then extract colors from crop
        crop_result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        crop_colors = extract_colors(crop_result["output_path"], n_colors=1)

        # Both should find pure red
        assert direct_result["colors"][0]["hex"] == "#FF0000"
        assert crop_colors["colors"][0]["hex"] == "#FF0000"

    def test_grid_image_can_be_cropped(self, synthetic_image: Path) -> None:
        """The grid overlay image should itself be croppable."""
        info = image_info(str(synthetic_image))
        grid_path = info["grid_image"]
        # The grid image is a PNG — crop it
        crop_result = crop_image(grid_path, 0.0, 0.0, 0.5, 0.5, padding=0)
        assert crop_result["width"] == 100
        assert crop_result["height"] == 50
        cropped = Image.open(crop_result["output_path"])
        assert cropped.size == (100, 50)
