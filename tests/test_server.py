"""Tests for server.py MCP tool wrappers.

These tests verify the server wrapper contract:
1. Tool functions return dicts that serialize to valid JSON.
2. JSON contains all expected fields.
3. Error inputs produce ValueError (caught by server wrapper as error JSON).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestImageInfoWrapper:
    """Tests for the image_info → get_image_coordinates_grid wrapper."""

    def test_returns_serializable_dict(self, synthetic_image: Path) -> None:
        from tools.crop import image_info

        result = image_info(str(synthetic_image))
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["width"] == 200
        assert parsed["height"] == 100
        assert "grid_image" in parsed

    def test_all_expected_fields_present(self, synthetic_image: Path) -> None:
        from tools.crop import image_info

        result = image_info(str(synthetic_image))
        expected_keys = {
            "width",
            "height",
            "aspect_ratio",
            "file_size_kb",
            "mode",
            "pixels_per_percent",
            "longer_axis",
            "grid_image",
        }
        assert set(result.keys()) == expected_keys

    def test_invalid_path_raises_value_error(self) -> None:
        from tools.crop import image_info

        with pytest.raises(ValueError, match="not found"):
            image_info("/nonexistent/image.png")


class TestCropImageWrapper:
    """Tests for the crop_image → crop_to_magnify_image wrapper."""

    def test_returns_serializable_dict(self, synthetic_image: Path) -> None:
        from tools.crop import crop_image

        result = crop_image(str(synthetic_image), 0.0, 0.0, 0.5, 1.0, padding=0)
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert "output_path" in parsed
        assert parsed["width"] == 100

    def test_invalid_path_raises_value_error(self) -> None:
        from tools.crop import crop_image

        with pytest.raises(ValueError, match="not found"):
            crop_image("/nonexistent/image.png", 0.0, 0.0, 1.0, 1.0)

    def test_invalid_coords_raises_value_error(self, synthetic_image: Path) -> None:
        from tools.crop import crop_image

        with pytest.raises(ValueError, match="must be less than"):
            crop_image(str(synthetic_image), 0.8, 0.0, 0.2, 1.0)


class TestExtractColorsWrapper:
    """Tests for the extract_colors wrapper."""

    def test_returns_serializable_dict(self, synthetic_image: Path) -> None:
        from tools.colors import extract_colors

        result = extract_colors(str(synthetic_image), n_colors=2)
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert "colors" in parsed
        assert len(parsed["colors"]) == 2

    def test_invalid_path_raises_value_error(self) -> None:
        from tools.colors import extract_colors

        with pytest.raises(ValueError, match="not found"):
            extract_colors("/nonexistent/image.png")


class TestServerWrapperPattern:
    """Verify the server error-handling contract.

    MCP server wrappers catch ValueError and Exception, returning
    {"error": "..."} JSON instead of raising. These tests verify
    that tool functions raise the right exceptions for the server
    to catch.
    """

    def test_value_error_produces_error_json(self, synthetic_image: Path) -> None:
        """Simulate what the server wrapper does on ValueError."""
        from tools.crop import crop_image

        try:
            crop_image(str(synthetic_image), 0.8, 0.0, 0.2, 1.0)
            pytest.fail("Expected ValueError")
        except ValueError as e:
            error_json = json.dumps({"error": str(e)})
            parsed = json.loads(error_json)
            assert "error" in parsed
            assert "must be less than" in parsed["error"]

    def test_corrupted_image_produces_value_error(self, tmp_path: Path) -> None:
        """A file with image extension but invalid content raises ValueError."""
        bad_file = tmp_path / "bad.png"
        bad_file.write_bytes(b"this is not a PNG")
        from tools.crop import image_info

        with pytest.raises(ValueError, match="Could not open image"):
            image_info(str(bad_file))
