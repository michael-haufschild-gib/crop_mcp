"""Tests for check_contrast tool — WCAG contrast ratio and color conversions."""

from __future__ import annotations

import pytest

from tools.contrast import (
    _contrast_ratio,
    _parse_hex,
    _relative_luminance,
    _rgb_to_hsl,
    _rgb_to_oklch,
    check_contrast,
)


class TestParseHex:
    """Hex color string parsing."""

    def test_with_hash(self) -> None:
        assert _parse_hex("#FF8800") == (255, 136, 0)

    def test_without_hash(self) -> None:
        assert _parse_hex("1A2B3C") == (26, 43, 60)

    def test_lowercase(self) -> None:
        assert _parse_hex("#aabbcc") == (170, 187, 204)

    def test_black(self) -> None:
        assert _parse_hex("#000000") == (0, 0, 0)

    def test_white(self) -> None:
        assert _parse_hex("#FFFFFF") == (255, 255, 255)

    def test_strips_whitespace(self) -> None:
        assert _parse_hex("  #FF0000  ") == (255, 0, 0)

    def test_invalid_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            _parse_hex("#GG0000")

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            _parse_hex("#12345")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            _parse_hex("#1234567")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            _parse_hex("")

    def test_just_hash_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            _parse_hex("#")


class TestRelativeLuminance:
    """WCAG 2.1 relative luminance."""

    def test_black(self) -> None:
        assert _relative_luminance(0, 0, 0) == 0.0

    def test_white(self) -> None:
        assert _relative_luminance(255, 255, 255) == pytest.approx(1.0, abs=0.001)

    def test_red(self) -> None:
        # Red has luminance 0.2126 (the R coefficient)
        assert _relative_luminance(255, 0, 0) == pytest.approx(0.2126, abs=0.001)

    def test_green(self) -> None:
        # Green has luminance 0.7152
        assert _relative_luminance(0, 255, 0) == pytest.approx(0.7152, abs=0.001)

    def test_blue(self) -> None:
        # Blue has luminance 0.0722
        assert _relative_luminance(0, 0, 255) == pytest.approx(0.0722, abs=0.001)


class TestContrastRatio:
    """WCAG 2.1 contrast ratio formula."""

    def test_black_on_white(self) -> None:
        lum_white = _relative_luminance(255, 255, 255)
        lum_black = _relative_luminance(0, 0, 0)
        assert _contrast_ratio(lum_white, lum_black) == 21.0

    def test_same_color(self) -> None:
        lum = _relative_luminance(128, 128, 128)
        assert _contrast_ratio(lum, lum) == 1.0

    def test_order_independent(self) -> None:
        lum1 = _relative_luminance(255, 255, 255)
        lum2 = _relative_luminance(0, 0, 128)
        assert _contrast_ratio(lum1, lum2) == _contrast_ratio(lum2, lum1)


class TestRgbToHsl:
    """RGB to HSL conversion."""

    def test_pure_red(self) -> None:
        hue, sat, lum = _rgb_to_hsl(255, 0, 0)
        assert hue == 0.0
        assert sat == 100.0
        assert lum == 50.0

    def test_pure_green(self) -> None:
        hue, sat, lum = _rgb_to_hsl(0, 255, 0)
        assert hue == 120.0
        assert sat == 100.0
        assert lum == 50.0

    def test_pure_blue(self) -> None:
        hue, sat, lum = _rgb_to_hsl(0, 0, 255)
        assert hue == 240.0
        assert sat == 100.0
        assert lum == 50.0

    def test_white(self) -> None:
        _hue, sat, lum = _rgb_to_hsl(255, 255, 255)
        assert sat == 0.0
        assert lum == 100.0

    def test_black(self) -> None:
        _hue, sat, lum = _rgb_to_hsl(0, 0, 0)
        assert sat == 0.0
        assert lum == 0.0

    def test_mid_gray(self) -> None:
        _hue, sat, lum = _rgb_to_hsl(128, 128, 128)
        assert sat == 0.0
        assert lum == pytest.approx(50.2, abs=0.1)


class TestRgbToOklch:
    """sRGB to OKLCH conversion against known reference values."""

    def test_white(self) -> None:
        light, chroma, _hue = _rgb_to_oklch(255, 255, 255)
        assert light == pytest.approx(1.0, abs=0.002)
        assert chroma < 0.001  # achromatic

    def test_black(self) -> None:
        light, chroma, _hue = _rgb_to_oklch(0, 0, 0)
        assert light == pytest.approx(0.0, abs=0.001)
        assert chroma < 0.001  # achromatic

    def test_pure_red(self) -> None:
        # Reference: L≈0.6280, C≈0.2577, H≈29.2°
        light, chroma, hue = _rgb_to_oklch(255, 0, 0)
        assert light == pytest.approx(0.6280, abs=0.01)
        assert chroma == pytest.approx(0.2577, abs=0.01)
        assert hue == pytest.approx(29.2, abs=1.0)

    def test_pure_green(self) -> None:
        # Reference: L≈0.8664, C≈0.2948, H≈142.5°
        light, chroma, hue = _rgb_to_oklch(0, 255, 0)
        assert light == pytest.approx(0.8664, abs=0.01)
        assert chroma == pytest.approx(0.2948, abs=0.01)
        assert hue == pytest.approx(142.5, abs=1.0)

    def test_pure_blue(self) -> None:
        # Reference: L≈0.4520, C≈0.3132, H≈264.1°
        light, chroma, hue = _rgb_to_oklch(0, 0, 255)
        assert light == pytest.approx(0.4520, abs=0.01)
        assert chroma == pytest.approx(0.3132, abs=0.01)
        assert hue == pytest.approx(264.1, abs=1.0)


class TestCheckContrast:
    """Full check_contrast integration."""

    def test_black_on_white(self) -> None:
        result = check_contrast("#FFFFFF", "#000000")
        assert result["contrast_ratio"] == 21.0
        assert result["wcag_aa"] is True
        assert result["wcag_aaa"] is True
        assert "PASS" in str(result["verdict"])

    def test_white_on_white(self) -> None:
        result = check_contrast("#FFFFFF", "#FFFFFF")
        assert result["contrast_ratio"] == 1.0
        assert result["wcag_aa"] is False
        assert result["wcag_aaa"] is False
        assert "FAIL" in str(result["verdict"])

    def test_low_contrast_fails_all(self) -> None:
        # Light gray on white — should fail everything
        result = check_contrast("#CCCCCC", "#FFFFFF")
        ratio = float(result["contrast_ratio"])  # type: ignore[arg-type]
        assert ratio < 3.0
        assert result["wcag_aa"] is False
        assert result["wcag_aaa"] is False

    def test_medium_contrast_passes_aa_only(self) -> None:
        # Find a pair with ratio between 4.5 and 7.0
        # #767676 on white is the classic AA boundary color (~4.54:1)
        result = check_contrast("#767676", "#FFFFFF")
        ratio = float(result["contrast_ratio"])  # type: ignore[arg-type]
        assert ratio >= 4.5
        assert ratio < 7.0
        assert result["wcag_aa"] is True
        assert result["wcag_aaa"] is False
        assert "PASS AA" in str(result["verdict"])
        assert "FAIL AAA" in str(result["verdict"])

    def test_large_text_relaxed_thresholds(self) -> None:
        # A ratio between 3.0 and 4.5 should fail AA normal but pass AA large
        # #959595 on white ≈ 3.18:1
        result_normal = check_contrast("#959595", "#FFFFFF", text_is_large=False)
        result_large = check_contrast("#959595", "#FFFFFF", text_is_large=True)
        assert result_normal["wcag_aa"] is False
        assert result_large["wcag_aa"] is True

    def test_fg_bg_order_preserves_labels(self) -> None:
        result = check_contrast("#FF0000", "#0000FF")
        fg = result["foreground"]
        bg = result["background"]
        assert isinstance(fg, dict)
        assert isinstance(bg, dict)
        assert fg["hex"] == "#FF0000"
        assert bg["hex"] == "#0000FF"

    def test_ratio_is_symmetric(self) -> None:
        r1 = check_contrast("#FF0000", "#0000FF")
        r2 = check_contrast("#0000FF", "#FF0000")
        assert r1["contrast_ratio"] == r2["contrast_ratio"]

    def test_color_info_has_correct_conversions(self) -> None:
        result = check_contrast("#FF0000", "#000000")
        fg = result["foreground"]
        assert isinstance(fg, dict)
        assert fg["hex"] == "#FF0000"
        assert fg["rgb"] == [255, 0, 0]
        assert fg["hsl"] == [0.0, 100.0, 50.0]
        oklch = fg["oklch"]
        assert isinstance(oklch, list)
        assert oklch[0] == pytest.approx(0.6280, abs=0.01)  # L

    def test_verdict_contains_ratio(self) -> None:
        result = check_contrast("#FFFFFF", "#000000")
        assert "21.0" in str(result["verdict"])

    def test_invalid_foreground_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            check_contrast("not-a-color", "#000000")

    def test_invalid_background_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            check_contrast("#FFFFFF", "xyz")

    def test_without_hash_accepted(self) -> None:
        result = check_contrast("FFFFFF", "000000")
        assert result["contrast_ratio"] == 21.0
