"""Tests for validate_image_path and validate_coordinates."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.validators import validate_coordinates, validate_image_path


class TestValidateImagePath:
    """Tests for validate_image_path."""

    def test_valid_png(self, synthetic_image: Path) -> None:
        result = validate_image_path(str(synthetic_image))
        assert result == synthetic_image.resolve()

    def test_valid_jpg_extension(self, tmp_path: Path) -> None:
        from PIL import Image

        img = Image.new("RGB", (10, 10))
        jpg_path = tmp_path / "test.jpg"
        img.save(str(jpg_path))
        result = validate_image_path(str(jpg_path))
        assert result == jpg_path.resolve()

    def test_valid_webp_extension(self, tmp_path: Path) -> None:
        from PIL import Image

        img = Image.new("RGB", (10, 10))
        webp_path = tmp_path / "test.webp"
        img.save(str(webp_path))
        result = validate_image_path(str(webp_path))
        assert result == webp_path.resolve()

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        fake = tmp_path / "nope.png"
        with pytest.raises(ValueError, match="not found"):
            validate_image_path(str(fake))

    def test_nonexistent_parent_dir(self) -> None:
        with pytest.raises(ValueError, match="directory"):
            validate_image_path("/no/such/dir/img.png")

    def test_directory_not_file(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Not a file"):
            validate_image_path(str(tmp_path))

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("not an image")
        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_image_path(str(txt))

    def test_suggests_similar_files(self, synthetic_image: Path) -> None:
        """When file not found but dir has images, error lists them."""
        fake = synthetic_image.parent / "wrong_name.png"
        with pytest.raises(ValueError, match="synthetic.png"):
            validate_image_path(str(fake))


class TestValidateCoordinates:
    """Tests for validate_coordinates."""

    def test_valid_full_image(self) -> None:
        validate_coordinates(0.0, 0.0, 1.0, 1.0)  # no exception

    def test_valid_small_region(self) -> None:
        validate_coordinates(0.1, 0.2, 0.3, 0.4)  # no exception

    def test_boundary_values(self) -> None:
        validate_coordinates(0.0, 0.0, 0.01, 0.01)  # no exception

    @pytest.mark.parametrize(
        "coord_name,kwargs",
        [  # type: ignore[untyped-decorator]
            ("x1", {"x1": -0.1, "y1": 0.0, "x2": 1.0, "y2": 1.0}),
            ("x2", {"x1": 0.0, "y1": 0.0, "x2": 1.1, "y2": 1.0}),
            ("y1", {"x1": 0.0, "y1": -0.5, "x2": 1.0, "y2": 1.0}),
            ("y2", {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 2.0}),
        ],
    )
    def test_out_of_range(self, coord_name: str, kwargs: dict[str, float]) -> None:
        with pytest.raises(ValueError, match="out of range"):
            validate_coordinates(**kwargs)

    def test_x1_equals_x2(self) -> None:
        with pytest.raises(ValueError, match="x1.*must be less than x2"):
            validate_coordinates(0.5, 0.0, 0.5, 1.0)

    def test_x1_greater_than_x2(self) -> None:
        with pytest.raises(ValueError, match="x1.*must be less than x2"):
            validate_coordinates(0.8, 0.0, 0.2, 1.0)

    def test_y1_equals_y2(self) -> None:
        with pytest.raises(ValueError, match="y1.*must be less than y2"):
            validate_coordinates(0.0, 0.5, 1.0, 0.5)

    def test_y1_greater_than_y2(self) -> None:
        with pytest.raises(ValueError, match="y1.*must be less than y2"):
            validate_coordinates(0.0, 0.9, 1.0, 0.1)

    def test_non_numeric_input(self) -> None:
        with pytest.raises(ValueError, match="must be a number"):
            validate_coordinates("a", 0.0, 1.0, 1.0)  # type: ignore[arg-type]
