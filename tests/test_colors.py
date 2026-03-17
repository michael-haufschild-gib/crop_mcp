"""Tests for extract_colors and _kmeans."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pytest

from tools.colors import _crop_to_region, _kmeans, extract_colors


class TestKmeans:
    """Tests for the internal _kmeans implementation."""

    def test_single_color(self) -> None:
        pixels = np.full((100, 3), [255, 0, 0], dtype=np.uint8)
        centers, _labels = _kmeans(pixels, k=1)
        assert len(centers) == 1
        np.testing.assert_array_almost_equal(centers[0], [255, 0, 0], decimal=0)

    def test_two_colors(self) -> None:
        red = np.full((50, 3), [255, 0, 0], dtype=np.uint8)
        blue = np.full((50, 3), [0, 0, 255], dtype=np.uint8)
        pixels = np.vstack([red, blue])
        centers, _labels = _kmeans(pixels, k=2)
        # Sort centers by red channel to ensure consistent order
        sorted_centers = centers[np.argsort(centers[:, 0])]
        np.testing.assert_array_almost_equal(sorted_centers[0], [0, 0, 255], decimal=0)
        np.testing.assert_array_almost_equal(sorted_centers[1], [255, 0, 0], decimal=0)

    def test_k_greater_than_unique_colors(self) -> None:
        """k > unique colors returns only unique colors without crash."""
        pixels = np.full((100, 3), [128, 128, 128], dtype=np.uint8)
        centers, _labels = _kmeans(pixels, k=5)
        assert len(centers) == 1  # Only one unique color

    def test_deterministic_with_seed(self) -> None:
        pixels = np.random.default_rng(0).integers(0, 256, (200, 3)).astype(np.uint8)
        c1, l1 = _kmeans(pixels, k=3)
        c2, l2 = _kmeans(pixels, k=3)
        np.testing.assert_array_equal(c1, c2)
        np.testing.assert_array_equal(l1, l2)

    def test_two_color_labels_approximately_equal(self) -> None:
        """Each color should get ~50% of labels."""
        red = np.full((100, 3), [255, 0, 0], dtype=np.uint8)
        blue = np.full((100, 3), [0, 0, 255], dtype=np.uint8)
        pixels = np.vstack([red, blue])
        centers, labels = _kmeans(pixels, k=2)
        counts = [int(np.sum(labels == i)) for i in range(len(centers))]
        assert all(c == 100 for c in counts)


class TestExtractColors:
    """Tests for extract_colors."""

    def test_two_colors_from_synthetic(self, synthetic_image: Path) -> None:
        result = extract_colors(str(synthetic_image), n_colors=2)
        hexes = {c["hex"] for c in result["colors"]}
        assert "#FF0000" in hexes
        assert "#0000FF" in hexes

    def test_region_left_half_only_red(self, synthetic_image: Path) -> None:
        result = extract_colors(str(synthetic_image), n_colors=2, x1=0.0, y1=0.0, x2=0.5, y2=1.0)
        hexes = {c["hex"] for c in result["colors"]}
        assert "#FF0000" in hexes
        assert "#0000FF" not in hexes

    def test_partial_region_raises(self, synthetic_image: Path) -> None:
        with pytest.raises(ValueError, match="Incomplete region"):
            extract_colors(str(synthetic_image), x1=0.0)

    def test_n_colors_zero_raises(self, synthetic_image: Path) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            extract_colors(str(synthetic_image), n_colors=0)

    def test_n_colors_too_high_raises(self, synthetic_image: Path) -> None:
        with pytest.raises(ValueError, match="too high"):
            extract_colors(str(synthetic_image), n_colors=21)

    def test_percentages_sum_to_100(self, synthetic_image: Path) -> None:
        result = extract_colors(str(synthetic_image), n_colors=2)
        total = sum(c["percentage"] for c in result["colors"])
        assert abs(total - 100.0) < 1.0

    def test_return_dict_keys(self, synthetic_image: Path) -> None:
        result = extract_colors(str(synthetic_image), n_colors=2)
        assert set(result.keys()) == {"colors", "image_size", "region_analyzed"}

    def test_color_entry_structure_and_values(self, synthetic_image: Path) -> None:
        result = extract_colors(str(synthetic_image), n_colors=2)
        for color in result["colors"]:
            # Verify hex format: #RRGGBB
            assert isinstance(color["hex"], str)
            assert len(color["hex"]) == 7
            assert color["hex"][0] == "#"
            int(color["hex"][1:], 16)  # raises ValueError if not valid hex
            # Verify RGB values are in valid range
            assert len(color["rgb"]) == 3
            assert all(0 <= v <= 255 for v in color["rgb"])
            # Verify percentage is a positive number
            assert 0.0 < color["percentage"] <= 100.0

    def test_solid_color_image(
        self,
        solid_color_image: Callable[[tuple[int, int, int], tuple[int, int]], Path],
    ) -> None:
        path = solid_color_image((0, 255, 0), (100, 100))
        result = extract_colors(str(path), n_colors=1)
        assert result["colors"][0]["hex"] == "#00FF00"
        assert result["colors"][0]["percentage"] == 100.0

    def test_large_image_downsampled(self, tmp_path: Path) -> None:
        """Images > MAX_ANALYSIS_DIM are downsampled without error."""
        from PIL import Image

        img = Image.new("RGB", (1000, 1000), (255, 0, 0))
        path = tmp_path / "large.png"
        img.save(str(path))
        result = extract_colors(str(path), n_colors=1)
        assert result["colors"][0]["hex"] == "#FF0000"


class TestCropToRegion:
    """Tests for _crop_to_region internal helper."""

    def test_crop_dimensions(self) -> None:
        from PIL import Image

        img = Image.new("RGB", (200, 100), (255, 0, 0))
        cropped, _description = _crop_to_region(img, 0.0, 0.0, 0.5, 1.0)
        assert cropped.size == (100, 100)

    def test_region_description_format(self) -> None:
        from PIL import Image

        img = Image.new("RGB", (200, 100))
        _, description = _crop_to_region(img, 0.1, 0.2, 0.3, 0.4)
        assert description == "(0.10, 0.20) to (0.30, 0.40)"

    def test_full_image_region(self) -> None:
        from PIL import Image

        img = Image.new("RGB", (200, 100))
        cropped, _ = _crop_to_region(img, 0.0, 0.0, 1.0, 1.0)
        assert cropped.size == (200, 100)
