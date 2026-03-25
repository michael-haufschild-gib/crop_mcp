"""Tests for server.py MCP tool wrappers and MCP wiring.

These tests verify:
1. Tool functions return dicts that serialize to valid JSON.
2. JSON contains all expected fields.
3. Error inputs produce ValueError (caught by server wrapper as error JSON).
4. MCP tool registration wires all four tools with correct names.
5. MCP tool invocation returns valid JSON strings through the server layer.
6. Unexpected exceptions are sanitized before reaching MCP clients.
7. main() entry point handles --setup flag and normal startup.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from server import _register_color_tools, _register_image_tools, _run_tool, main


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


def _mcp_result_text(result: object) -> str:
    """Extract the JSON text from a FastMCP call_tool result.

    call_tool returns (list[TextContent], dict). The first TextContent
    block contains the JSON string returned by the tool wrapper.
    """
    content_blocks = result[0]  # type: ignore[index]
    return str(content_blocks[0].text)


class TestMCPWiring:
    """Tests that verify the actual MCP server layer — tool registration,
    invocation through FastMCP, and JSON serialization."""

    @pytest.fixture()  # type: ignore[untyped-decorator]
    def mcp(self) -> FastMCP:
        """Create a FastMCP instance with all tools registered."""
        server = FastMCP(name="test-vision-tools")
        _register_image_tools(server)
        _register_color_tools(server)
        return server

    def test_all_four_tools_registered(self, mcp: FastMCP, synthetic_image: Path) -> None:
        """Verify all expected tools are registered by calling each through the public API."""
        expected_tools = {
            "get_image_coordinates_grid": {"image_path": str(synthetic_image)},
            "crop_to_magnify_image": {
                "image_path": str(synthetic_image),
                "x1": 0.0,
                "y1": 0.0,
                "x2": 1.0,
                "y2": 1.0,
                "padding": 0,
            },
            "extract_colors": {"image_path": str(synthetic_image), "n_colors": 2},
            "check_contrast": {"foreground": "#FFFFFF", "background": "#000000"},
        }
        for name, args in expected_tools.items():
            result = asyncio.run(mcp.call_tool(name, args))
            parsed = json.loads(_mcp_result_text(result))
            assert "error" not in parsed, f"Tool '{name}' returned error: {parsed.get('error')}"

    def test_registration_rejects_non_fastmcp(self) -> None:
        with pytest.raises(TypeError, match="Expected FastMCP"):
            _register_image_tools("not a FastMCP")

    def test_image_info_returns_json_via_mcp(self, mcp: FastMCP, synthetic_image: Path) -> None:
        result = asyncio.run(
            mcp.call_tool(
                "get_image_coordinates_grid",
                {"image_path": str(synthetic_image)},
            )
        )
        parsed = json.loads(_mcp_result_text(result))
        assert parsed["width"] == 200
        assert parsed["height"] == 100
        assert "grid_image" in parsed

    def test_crop_returns_json_via_mcp(self, mcp: FastMCP, synthetic_image: Path) -> None:
        result = asyncio.run(
            mcp.call_tool(
                "crop_to_magnify_image",
                {
                    "image_path": str(synthetic_image),
                    "x1": 0.0,
                    "y1": 0.0,
                    "x2": 0.5,
                    "y2": 1.0,
                    "padding": 0,
                },
            )
        )
        parsed = json.loads(_mcp_result_text(result))
        assert parsed["width"] == 100
        assert parsed["height"] == 100
        assert Path(parsed["output_path"]).exists()

    def test_extract_colors_returns_json_via_mcp(self, mcp: FastMCP, synthetic_image: Path) -> None:
        result = asyncio.run(
            mcp.call_tool(
                "extract_colors",
                {"image_path": str(synthetic_image), "n_colors": 2},
            )
        )
        parsed = json.loads(_mcp_result_text(result))
        hexes = {c["hex"] for c in parsed["colors"]}
        assert "#FF0000" in hexes
        assert "#0000FF" in hexes

    def test_check_contrast_returns_json_via_mcp(self, mcp: FastMCP) -> None:
        result = asyncio.run(
            mcp.call_tool(
                "check_contrast",
                {"foreground": "#FFFFFF", "background": "#000000"},
            )
        )
        parsed = json.loads(_mcp_result_text(result))
        assert parsed["contrast_ratio"] == 21.0
        assert parsed["wcag_aa"] is True

    def test_invalid_input_returns_error_json_via_mcp(self, mcp: FastMCP) -> None:
        """Invalid path should return error JSON, not raise."""
        result = asyncio.run(
            mcp.call_tool(
                "get_image_coordinates_grid",
                {"image_path": "/nonexistent/image.png"},
            )
        )
        parsed = json.loads(_mcp_result_text(result))
        assert "error" in parsed
        assert "not found" in parsed["error"]

    def test_invalid_contrast_returns_error_json_via_mcp(self, mcp: FastMCP) -> None:
        result = asyncio.run(
            mcp.call_tool(
                "check_contrast",
                {"foreground": "not-a-color", "background": "#000000"},
            )
        )
        parsed = json.loads(_mcp_result_text(result))
        assert "error" in parsed
        assert "Invalid hex color" in parsed["error"]


class TestRunToolErrorSanitization:
    """Tests that _run_tool sanitizes unexpected exception details."""

    def test_value_error_preserves_message(self) -> None:
        def failing_tool() -> None:
            raise ValueError("helpful user message")

        result = json.loads(_run_tool("test_tool", failing_tool))
        assert result["error"] == "helpful user message"

    def test_unexpected_error_is_sanitized(self) -> None:
        def crashing_tool() -> None:
            raise RuntimeError("internal traceback detail at /secret/path")

        result = json.loads(_run_tool("test_tool", crashing_tool))
        assert "internal traceback" not in result["error"]
        assert "/secret/path" not in result["error"]
        assert result["error"] == "Internal error in test_tool. Check logs."


class TestMain:
    """Tests for the main() entry point."""

    def test_setup_flag_calls_execv(self, tmp_path: Path) -> None:
        script = tmp_path / "setup.sh"
        script.touch()
        # os.execv replaces the process; mock raises OSError to stop fallthrough
        with (
            patch("sys.argv", ["server.py", "--setup"]),
            patch("server.SETUP_SCRIPT", script),
            patch("os.execv", side_effect=OSError("mock execv")) as mock_execv,
            pytest.raises(OSError, match="mock execv"),
        ):
            main()
        mock_execv.assert_called_once()
        assert mock_execv.call_args[0][0] == "/bin/bash"
        assert str(script) in mock_execv.call_args[0][1]

    def test_setup_flag_exits_when_script_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.sh"
        with (
            patch("sys.argv", ["server.py", "--setup"]),
            patch("server.SETUP_SCRIPT", missing),
            pytest.raises(SystemExit, match="1"),
        ):
            main()

    def test_normal_startup_calls_ensure_and_start(self) -> None:
        with (
            patch("sys.argv", ["server.py"]),
            patch("server.ensure_dependencies"),
            patch("server._start_server") as mock_start,
        ):
            main()
            mock_start.assert_called_once()
