"""Tests for _validate_region in tools/colors.py."""

from __future__ import annotations

import pytest

from tools.colors import _validate_region


class TestValidateRegion:
    """Tests for the optional region coordinate validator."""

    def test_all_none_returns_none(self) -> None:
        assert _validate_region(None, None, None, None) is None

    def test_all_provided_returns_tuple(self) -> None:
        result = _validate_region(0.0, 0.0, 1.0, 1.0)
        assert result == (0.0, 0.0, 1.0, 1.0)

    def test_partial_x1_only_raises(self) -> None:
        with pytest.raises(ValueError, match="Incomplete region"):
            _validate_region(0.1, None, None, None)

    def test_partial_y2_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="y2"):
            _validate_region(0.0, 0.0, 1.0, None)

    def test_partial_x1_y1_only_raises(self) -> None:
        with pytest.raises(ValueError, match="Incomplete region"):
            _validate_region(0.0, 0.0, None, None)

    def test_valid_region_delegates_to_validate_coordinates(self) -> None:
        with pytest.raises(ValueError, match="must be less than"):
            _validate_region(0.8, 0.0, 0.2, 1.0)

    def test_out_of_range_region_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            _validate_region(0.0, 0.0, 1.5, 1.0)

    def test_returned_tuple_matches_input(self) -> None:
        result = _validate_region(0.1, 0.2, 0.3, 0.4)
        assert result == (0.1, 0.2, 0.3, 0.4)
