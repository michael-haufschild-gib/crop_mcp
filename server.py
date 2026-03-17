#!/usr/bin/env python3
"""Vision Tools MCP Server — gives Claude Code image crop and color extraction tools.

Usage:
    python3 server.py              # Normal: run as MCP server (stdio)
    python3 server.py --setup      # Run setup only (create venv + install deps)
    python3 server.py --test       # Quick self-test of both tools
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger("vision-tools")

VENV_DIR = Path.home() / ".vision-tools-env"
VENV_PYTHON = VENV_DIR / "bin" / "python3"
SETUP_SCRIPT = Path(__file__).parent / "setup.sh"


def _check_dependencies() -> str | None:
    """Check if all required packages are importable. Returns error message or None."""
    missing = []
    try:
        import mcp  # noqa: F401
    except ImportError:
        missing.append("mcp")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")

    if missing:
        return (
            f"Missing packages: {', '.join(missing)}\n"
            f"\n"
            f"Run the setup script to install everything:\n"
            f"  bash {SETUP_SCRIPT}\n"
            f"\n"
            f"Or install manually into the venv:\n"
            f"  {VENV_DIR}/bin/pip3 install {' '.join(missing)}\n"
        )
    return None


def _auto_setup() -> bool:
    """Attempt automatic setup if the venv doesn't exist. Returns True if setup ran."""
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        return False  # Venv exists, deps might just be missing

    if not SETUP_SCRIPT.exists():
        return False

    _log.info("First run — setting up virtualenv...")
    try:
        result = subprocess.run(
            ["bash", str(SETUP_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            _log.info("Setup complete!")
            return True
        _log.error("Setup failed:\n%s", result.stderr)
        return False
    except Exception as e:
        _log.error("Setup error: %s", e)
        return False


def _relaunch_in_venv() -> None:
    """Re-launch this script using the venv Python if we're not already in it."""
    # Already in venv?
    if sys.prefix != sys.base_prefix:
        return
    if not VENV_PYTHON.exists():
        return

    # Re-exec with venv python
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


def _run_self_test() -> None:
    """Quick self-test: create a test image, crop it, extract colors."""
    import tempfile

    from PIL import Image

    print("Running self-test...")

    # Create a test image: left half red, right half blue
    img = Image.new("RGB", (200, 100))
    img.paste(Image.new("RGB", (100, 100), (255, 0, 0)), (0, 0))
    img.paste(Image.new("RGB", (100, 100), (0, 0, 255)), (100, 0))

    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = str(Path(tmpdir) / "test.png")
        img.save(test_path)

        # Test image_info
        from tools.crop import crop_image, image_info

        info = image_info(test_path)
        print(f"  image_info: {info['width']}x{info['height']}, ratio={info['aspect_ratio']}")
        assert info["width"] == 200, f"Expected width 200, got {info['width']}"
        assert info["height"] == 100, f"Expected height 100, got {info['height']}"
        assert info["aspect_ratio"] == 2.0, f"Expected ratio 2.0, got {info['aspect_ratio']}"
        assert "grid_image" in info, "Missing grid_image in image_info result"
        assert Path(info["grid_image"]).exists(), f"Grid image not found: {info['grid_image']}"
        print(f"  grid_image: {info['grid_image']}")

        # Test crop
        result = crop_image(test_path, 0.0, 0.0, 0.5, 1.0, padding=0)
        print(f"  crop_image: {result['width']}x{result['height']} -> {result['output_path']}")
        assert result["width"] == 100, f"Expected width 100, got {result['width']}"
        assert result["height"] == 100, f"Expected height 100, got {result['height']}"
        assert result["source_width"] == 200, (
            f"Expected source_width 200, got {result['source_width']}"
        )
        assert result["source_height"] == 100, (
            f"Expected source_height 100, got {result['source_height']}"
        )
        assert "crop_region_px" in result, "Missing crop_region_px in result"
        assert "crop_region_normalized" in result, "Missing crop_region_normalized in result"

        # Test colors
        from tools.colors import extract_colors

        result = extract_colors(test_path, n_colors=2)
        print(f"  extract_colors: {len(result['colors'])} colors found")
        hexes = {c["hex"] for c in result["colors"]}
        assert "#FF0000" in hexes, f"Expected #FF0000 in {hexes}"
        assert "#0000FF" in hexes, f"Expected #0000FF in {hexes}"

        # Test check_contrast
        from tools.contrast import check_contrast

        result = check_contrast("#FFFFFF", "#000000")
        print(f"  check_contrast: ratio={result['contrast_ratio']}, verdict={result['verdict']}")
        assert result["contrast_ratio"] == 21.0, (
            f"Expected ratio 21.0, got {result['contrast_ratio']}"
        )
        assert result["wcag_aa"] is True, "Expected AA pass for black on white"
        assert result["wcag_aaa"] is True, "Expected AAA pass for black on white"

    print("All tests passed!")


def _ensure_dependencies() -> None:
    """Ensure venv exists and dependencies are installed. Exits on failure."""
    _relaunch_in_venv()

    if _check_dependencies():
        if _auto_setup():
            _relaunch_in_venv()

        err = _check_dependencies()
        if err:
            _log.error("%s", err)
            sys.exit(1)


def _register_image_tools(mcp_server: object) -> None:  # noqa: C901
    """Register image-based MCP tools (grid, crop, colors)."""
    from mcp.server.fastmcp import FastMCP

    if not isinstance(mcp_server, FastMCP):
        raise TypeError(f"Expected FastMCP instance, got {type(mcp_server).__name__}")

    from tools.colors import extract_colors as _extract_colors
    from tools.crop import crop_image as _crop_image
    from tools.crop import image_info as _image_info

    @mcp_server.tool(  # type: ignore[untyped-decorator]
        name="get_image_coordinates_grid",
        description=(
            "Get image dimensions and a coordinate-reference grid overlay for "
            "planning crops. Returns metadata and grid_image — a copy with "
            "labeled gridlines (.1 through .9). Read the grid_image to see where "
            "normalized coordinates fall before cropping. On tall/wide images, "
            "errors on the longer axis displace more pixels."
        ),
    )
    def image_info(image_path: str) -> str:
        """Get image dimensions and metadata.

        Args:
            image_path: Absolute path to the image file.
        """
        _log.info("tool=get_image_coordinates_grid path=%s", image_path)
        t0 = time.monotonic()
        try:
            result = _image_info(image_path=image_path)
            _log.info("tool=get_image_coordinates_grid duration=%.3fs", time.monotonic() - t0)
            return json.dumps(result)
        except ValueError as e:
            _log.error("tool=get_image_coordinates_grid error=%s", e)
            return json.dumps({"error": str(e)})
        except Exception as e:
            _log.error("tool=get_image_coordinates_grid error=%s", e)
            return json.dumps({"error": f"Unexpected error: {e}"})

    @mcp_server.tool(  # type: ignore[untyped-decorator]
        name="crop_to_magnify_image",
        description=(
            "Crop a region from a screenshot or image and save it as a new "
            "file. Use this as a magnifying glass when you cannot clearly read "
            "text, distinguish UI elements, or verify visual details in an "
            "image — crop the area and read the result for a closer look. Also "
            "use when a user asks you to crop. Coordinates are normalized 0-1 "
            "where (0,0) is top-left and (1,1) is bottom-right. Returns the "
            "cropped image path plus source dimensions and the exact "
            "pixel/normalized region that was cropped (accounting for padding), "
            "so you can refine with a second crop if needed. Call image_info "
            "first to read its grid_image for accurate coordinates."
        ),
    )
    def crop_image(
        image_path: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        output_path: str | None = None,
        padding: int = 20,
    ) -> str:
        """Crop a region from an image.

        Args:
            image_path: Absolute path to the source image file.
            x1: Left edge of crop region (0.0 = left, 1.0 = right).
            y1: Top edge of crop region (0.0 = top, 1.0 = bottom).
            x2: Right edge of crop region. Must be > x1.
            y2: Bottom edge of crop region. Must be > y1.
            output_path: Where to save. Defaults to a path next to source.
            padding: Extra pixels around the crop region. Default: 20.
        """
        _log.info(
            "tool=crop_to_magnify_image path=%s region=(%.2f,%.2f)-(%.2f,%.2f)",
            image_path,
            x1,
            y1,
            x2,
            y2,
        )
        t0 = time.monotonic()
        try:
            result = _crop_image(
                image_path=image_path,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                output_path=output_path,
                padding=padding,
            )
            _log.info("tool=crop_to_magnify_image duration=%.3fs", time.monotonic() - t0)
            return json.dumps(result)
        except ValueError as e:
            _log.error("tool=crop_to_magnify_image error=%s", e)
            return json.dumps({"error": str(e)})
        except Exception as e:
            _log.error("tool=crop_to_magnify_image error=%s", e)
            return json.dumps({"error": f"Unexpected error: {e}"})

    @mcp_server.tool(  # type: ignore[untyped-decorator]
        name="extract_colors",
        description=(
            "Extract dominant colors from an image or image region as exact "
            "hex values. Use when you need precise CSS color codes from a "
            "screenshot, design mockup, or reference image — do NOT guess hex "
            "values from visual inspection. Optionally specify a region using "
            "normalized 0-1 coordinates. Returns hex codes, RGB values, and "
            "the percentage of the image each color occupies."
        ),
    )
    def extract_colors(
        image_path: str,
        n_colors: int = 6,
        x1: float | None = None,
        y1: float | None = None,
        x2: float | None = None,
        y2: float | None = None,
    ) -> str:
        """Extract dominant colors from an image.

        Args:
            image_path: Absolute path to the source image file.
            n_colors: Dominant colors to extract. Default: 6. Range: 1-20.
            x1: Left edge of region (0.0-1.0). Omit all four for full image.
            y1: Top edge of region (0.0-1.0).
            x2: Right edge of region (0.0-1.0).
            y2: Bottom edge of region (0.0-1.0).
        """
        _log.info("tool=extract_colors path=%s n_colors=%d", image_path, n_colors)
        t0 = time.monotonic()
        try:
            result = _extract_colors(
                image_path=image_path,
                n_colors=n_colors,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )
            _log.info("tool=extract_colors duration=%.3fs", time.monotonic() - t0)
            return json.dumps(result)
        except ValueError as e:
            _log.error("tool=extract_colors error=%s", e)
            return json.dumps({"error": str(e)})
        except Exception as e:
            _log.error("tool=extract_colors error=%s", e)
            return json.dumps({"error": f"Unexpected error: {e}"})


def _register_color_tools(mcp_server: object) -> None:
    """Register color analysis MCP tools (contrast)."""
    from mcp.server.fastmcp import FastMCP

    if not isinstance(mcp_server, FastMCP):
        raise TypeError(f"Expected FastMCP instance, got {type(mcp_server).__name__}")

    from tools.contrast import check_contrast as _check_contrast

    @mcp_server.tool(  # type: ignore[untyped-decorator]
        name="check_contrast",
        description=(
            "Compute WCAG contrast ratio between two hex colors and get "
            "color space conversions (RGB, HSL, OKLCH). Use when you have "
            "two colors (e.g. from extract_colors) and need the exact "
            "contrast ratio for accessibility review, or need a hex color "
            "converted to OKLCH/HSL. Do NOT guess contrast ratios or color "
            "conversions — use this tool."
        ),
    )
    def check_contrast(
        foreground: str,
        background: str,
        text_is_large: bool = False,
    ) -> str:
        """Compute WCAG contrast ratio and color conversions.

        Args:
            foreground: Text color as hex, e.g. "#FFFFFF" or "FFFFFF".
            background: Background color as hex, e.g. "#1A1A2E" or "1A1A2E".
            text_is_large: True if text is >=18pt or >=14pt bold.
        """
        _log.info(
            "tool=check_contrast fg=%s bg=%s large=%s",
            foreground,
            background,
            text_is_large,
        )
        t0 = time.monotonic()
        try:
            result = _check_contrast(
                foreground=foreground,
                background=background,
                text_is_large=text_is_large,
            )
            _log.info("tool=check_contrast duration=%.3fs", time.monotonic() - t0)
            return json.dumps(result)
        except ValueError as e:
            _log.error("tool=check_contrast error=%s", e)
            return json.dumps({"error": str(e)})
        except Exception as e:
            _log.error("tool=check_contrast error=%s", e)
            return json.dumps({"error": f"Unexpected error: {e}"})


def _start_server() -> None:
    """Register MCP tools and start the stdio server."""
    from mcp.server.fastmcp import FastMCP

    mcp_server = FastMCP(name="vision-tools")
    _register_image_tools(mcp_server)
    _register_color_tools(mcp_server)
    mcp_server.run(transport="stdio")


def main() -> None:
    if "--setup" in sys.argv:
        if SETUP_SCRIPT.exists():
            os.execv("/bin/bash", ["/bin/bash", str(SETUP_SCRIPT)])
        else:
            _log.error("Setup script not found: %s", SETUP_SCRIPT)
            sys.exit(1)

    _ensure_dependencies()

    if "--test" in sys.argv:
        _run_self_test()
        return

    _start_server()


if __name__ == "__main__":
    main()
