"""check_contrast tool — WCAG contrast ratio and color space conversions."""

from __future__ import annotations

import math
import re
from typing import TypedDict

__all__ = ["check_contrast"]

# sRGB linearization threshold (IEC 61966-2-1)
_SRGB_LINEAR_THRESHOLD = 0.04045

# HSL saturation formula midpoint
_HSL_MID = 0.5

# OKLCH achromatic chroma threshold — below this, hue is meaningless
_ACHROMATIC_THRESHOLD = 0.0002

# --- Hex parsing ---

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


class ColorInfo(TypedDict):
    """Color with representations in multiple color spaces."""

    hex: str
    rgb: list[int]
    hsl: list[float]
    oklch: list[float]


class ContrastResult(TypedDict):
    """Return type for check_contrast."""

    foreground: ColorInfo
    background: ColorInfo
    contrast_ratio: float
    wcag_aa: bool
    wcag_aaa: bool
    verdict: str


def _parse_hex(hex_str: str) -> tuple[int, int, int]:
    """Parse a hex color string to (R, G, B) integers.

    Args:
        hex_str: Color string like "#FF8800" or "FF8800".

    Returns:
        Tuple of (R, G, B) each in 0-255.

    Raises:
        ValueError: If the string is not a valid 6-digit hex color.
    """
    m = _HEX_RE.match(hex_str.strip())
    if not m:
        raise ValueError(
            f"Invalid hex color: '{hex_str}'.\n"
            f"Expected format: '#RRGGBB' or 'RRGGBB' (6 hex digits).\n"
            f"Examples: '#FF8800', '1A1A2E', '#ffffff'"
        )
    digits = m.group(1)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB 0-255 to uppercase hex string with '#' prefix."""
    return f"#{r:02X}{g:02X}{b:02X}"


# --- sRGB linearization ---


def _srgb_to_linear(c: float) -> float:
    """Convert a single sRGB component (0-1) to linear light.

    Args:
        c: sRGB component in 0.0-1.0 range.

    Returns:
        Linear-light value.
    """
    if c <= _SRGB_LINEAR_THRESHOLD:
        return c / 12.92
    return float(((c + 0.055) / 1.055) ** 2.4)


# --- WCAG 2.1 relative luminance and contrast ---


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Compute WCAG 2.1 relative luminance from sRGB 0-255.

    Args:
        r: Red channel 0-255.
        g: Green channel 0-255.
        b: Blue channel 0-255.

    Returns:
        Relative luminance (0.0 = black, 1.0 = white).
    """
    rl = _srgb_to_linear(r / 255.0)
    gl = _srgb_to_linear(g / 255.0)
    bl = _srgb_to_linear(b / 255.0)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def _contrast_ratio(lum1: float, lum2: float) -> float:
    """Compute WCAG 2.1 contrast ratio between two luminances.

    Args:
        lum1: Relative luminance of first color.
        lum2: Relative luminance of second color.

    Returns:
        Contrast ratio (1.0 to 21.0), rounded to 2 decimal places.
    """
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


# --- HSL conversion ---


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB 0-255 to HSL.

    Args:
        r: Red channel 0-255.
        g: Green channel 0-255.
        b: Blue channel 0-255.

    Returns:
        (H 0-360, S 0-100, L 0-100), each rounded to 1 decimal place.
    """
    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    # Lightness
    light = (cmax + cmin) / 2.0

    if delta == 0.0:
        return (0.0, 0.0, round(light * 100, 1))

    # Saturation
    sat = delta / (cmax + cmin) if light <= _HSL_MID else delta / (2.0 - cmax - cmin)

    # Hue
    if cmax == rf:
        hue = ((gf - bf) / delta) % 6.0
    elif cmax == gf:
        hue = (bf - rf) / delta + 2.0
    else:
        hue = (rf - gf) / delta + 4.0
    hue *= 60.0
    if hue < 0:
        hue += 360.0

    return (round(hue, 1), round(sat * 100, 1), round(light * 100, 1))


# --- OKLab / OKLCH conversion ---

# Björn Ottosson's direct sRGB→LMS matrix (pre-multiplied sRGB→XYZ→LMS)
_M1 = [
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
]

# Cube-root LMS → OKLab
_M2 = [
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
]


def _rgb_to_oklch(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert sRGB 0-255 to OKLCH.

    Args:
        r: Red channel 0-255.
        g: Green channel 0-255.
        b: Blue channel 0-255.

    Returns:
        (L, C, H) where L is 0-1, C is chroma (unbounded positive),
        H is hue 0-360. L and C rounded to 4 decimal places, H to 1.
        For achromatic colors (C < 0.0002), H is 0.0.
    """
    # sRGB → linear
    rl = _srgb_to_linear(r / 255.0)
    gl = _srgb_to_linear(g / 255.0)
    bl = _srgb_to_linear(b / 255.0)

    # Linear sRGB → LMS
    l_ = _M1[0][0] * rl + _M1[0][1] * gl + _M1[0][2] * bl
    m_ = _M1[1][0] * rl + _M1[1][1] * gl + _M1[1][2] * bl
    s_ = _M1[2][0] * rl + _M1[2][1] * gl + _M1[2][2] * bl

    # Cube root
    l_cr = math.copysign(abs(l_) ** (1.0 / 3.0), l_) if l_ != 0.0 else 0.0
    m_cr = math.copysign(abs(m_) ** (1.0 / 3.0), m_) if m_ != 0.0 else 0.0
    s_cr = math.copysign(abs(s_) ** (1.0 / 3.0), s_) if s_ != 0.0 else 0.0

    # OKLab
    ok_l = _M2[0][0] * l_cr + _M2[0][1] * m_cr + _M2[0][2] * s_cr
    ok_a = _M2[1][0] * l_cr + _M2[1][1] * m_cr + _M2[1][2] * s_cr
    ok_b = _M2[2][0] * l_cr + _M2[2][1] * m_cr + _M2[2][2] * s_cr

    # OKLab → OKLCH (polar)
    chroma = math.sqrt(ok_a * ok_a + ok_b * ok_b)

    if chroma < _ACHROMATIC_THRESHOLD:
        hue = 0.0
    else:
        hue = math.degrees(math.atan2(ok_b, ok_a))
        if hue < 0:
            hue += 360.0

    return (round(ok_l, 4), round(chroma, 4), round(hue, 1))


# --- Public API ---


def _color_info(hex_str: str) -> ColorInfo:
    """Build color info dict with all color space representations.

    Args:
        hex_str: Hex color string like "#FF8800" or "FF8800".

    Returns:
        Dict with hex, rgb, hsl, oklch keys.
    """
    r, g, b = _parse_hex(hex_str)
    return {
        "hex": _rgb_to_hex(r, g, b),
        "rgb": [r, g, b],
        "hsl": list(_rgb_to_hsl(r, g, b)),
        "oklch": list(_rgb_to_oklch(r, g, b)),
    }


# WCAG 2.1 thresholds
_AA_NORMAL = 4.5
_AA_LARGE = 3.0
_AAA_NORMAL = 7.0
_AAA_LARGE = 4.5


def check_contrast(
    foreground: str,
    background: str,
    text_is_large: bool = False,
) -> ContrastResult:
    """Compute WCAG contrast ratio between two colors with color space conversions.

    Args:
        foreground: Foreground (text) color as hex, e.g. "#FFFFFF" or "FFFFFF".
        background: Background color as hex, e.g. "#1A1A2E" or "1A1A2E".
        text_is_large: True if text is >=18pt or >=14pt bold. Uses relaxed
            WCAG thresholds (3:1 AA, 4.5:1 AAA instead of 4.5:1 / 7:1).

    Returns:
        Dict with foreground/background color info, contrast_ratio,
        wcag_aa, wcag_aaa booleans, and a verdict string.
    """
    fg_r, fg_g, fg_b = _parse_hex(foreground)
    bg_r, bg_g, bg_b = _parse_hex(background)

    fg_lum = _relative_luminance(fg_r, fg_g, fg_b)
    bg_lum = _relative_luminance(bg_r, bg_g, bg_b)
    ratio = _contrast_ratio(fg_lum, bg_lum)

    aa_threshold = _AA_LARGE if text_is_large else _AA_NORMAL
    aaa_threshold = _AAA_LARGE if text_is_large else _AAA_NORMAL
    size_label = "large" if text_is_large else "normal"

    passes_aa = ratio >= aa_threshold
    passes_aaa = ratio >= aaa_threshold

    if passes_aaa:
        verdict = f"PASS AA+AAA — {ratio}:1 ({size_label} text)"
    elif passes_aa:
        verdict = (
            f"PASS AA, FAIL AAA — {ratio}:1 "
            f"(AA needs {aa_threshold}:1, AAA needs {aaa_threshold}:1 for {size_label} text)"
        )
    else:
        verdict = f"FAIL — {ratio}:1 is below AA threshold ({aa_threshold}:1 for {size_label} text)"

    return {
        "foreground": _color_info(foreground),
        "background": _color_info(background),
        "contrast_ratio": ratio,
        "wcag_aa": passes_aa,
        "wcag_aaa": passes_aaa,
        "verdict": verdict,
    }
