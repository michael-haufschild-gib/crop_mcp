#!/usr/bin/env python3
"""Vision Tools MCP Server — gives Claude Code image crop and color extraction tools.

Usage:
    python3 server.py              # Normal: run as MCP server (stdio)
    python3 server.py --setup      # Run setup only (create venv + install deps)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import TYPE_CHECKING

from bootstrap import SETUP_SCRIPT, ensure_dependencies

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger("vision-tools")


def _run_tool(tool_name: str, fn: Callable[..., Any], **kwargs: Any) -> str:
    """Run a tool implementation with error handling, logging, and JSON serialization.

    All MCP tool wrappers delegate here. Handles timing, structured logging,
    and converts exceptions to error JSON so the server never crashes.

    Args:
        tool_name: MCP tool name for log lines.
        fn: Tool implementation function (from tools/ package).
        **kwargs: Arguments forwarded to fn.

    Returns:
        JSON string: the tool result dict, or ``{"error": "..."}``.
    """
    t0 = time.monotonic()
    try:
        result = fn(**kwargs)
        _log.info("tool=%s duration=%.3fs", tool_name, time.monotonic() - t0)
        return json.dumps(result)
    except ValueError as e:
        _log.error("tool=%s error=%s", tool_name, e)
        return json.dumps({"error": str(e)})
    except Exception as e:
        _log.error("tool=%s unexpected error=%s", tool_name, e, exc_info=True)
        return json.dumps({"error": f"Internal error in {tool_name}. Check logs."})


def _validate_mcp_server(mcp_server: object) -> None:
    """Raise TypeError if mcp_server is not a FastMCP instance."""
    from mcp.server.fastmcp import FastMCP as _FastMCP

    if not isinstance(mcp_server, _FastMCP):
        raise TypeError(f"Expected FastMCP instance, got {type(mcp_server).__name__}")


def _register_grid_tool(mcp_server: FastMCP) -> None:
    """Register the get_image_coordinates_grid tool."""
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
        return _run_tool("get_image_coordinates_grid", _image_info, image_path=image_path)


def _register_crop_tool(mcp_server: FastMCP) -> None:
    """Register the crop_to_magnify_image tool."""
    from tools.crop import crop_image as _crop_image

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
        return _run_tool(
            "crop_to_magnify_image",
            _crop_image,
            image_path=image_path,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            output_path=output_path,
            padding=padding,
        )


def _register_colors_tool(mcp_server: FastMCP) -> None:
    """Register the extract_colors tool."""
    from tools.colors import extract_colors as _extract_colors

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
        return _run_tool(
            "extract_colors",
            _extract_colors,
            image_path=image_path,
            n_colors=n_colors,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
        )


def _register_contrast_tool(mcp_server: FastMCP) -> None:
    """Register the check_contrast tool."""
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
        return _run_tool(
            "check_contrast",
            _check_contrast,
            foreground=foreground,
            background=background,
            text_is_large=text_is_large,
        )


def _register_image_tools(mcp_server: object) -> None:
    """Register image-based MCP tools (grid, crop, colors)."""
    _validate_mcp_server(mcp_server)
    _register_grid_tool(mcp_server)
    _register_crop_tool(mcp_server)
    _register_colors_tool(mcp_server)


def _register_color_tools(mcp_server: object) -> None:
    """Register color analysis MCP tools (contrast)."""
    _validate_mcp_server(mcp_server)
    _register_contrast_tool(mcp_server)


def _start_server() -> None:
    """Register MCP tools and start the stdio server."""
    from mcp.server.fastmcp import FastMCP

    mcp_server = FastMCP(name="vision-tools")
    _register_image_tools(mcp_server)
    _register_color_tools(mcp_server)
    mcp_server.run(transport="stdio")


def main() -> None:
    """Entry point: handle CLI flags and start the server."""
    if "--setup" in sys.argv:
        if SETUP_SCRIPT.exists():
            os.execv("/bin/bash", ["/bin/bash", str(SETUP_SCRIPT)])
        else:
            _log.error("Setup script not found: %s", SETUP_SCRIPT)
            sys.exit(1)

    ensure_dependencies()
    _start_server()


if __name__ == "__main__":
    main()
