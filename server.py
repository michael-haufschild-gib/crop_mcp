#!/usr/bin/env python3
"""Vision Tools MCP. The host owns the stdio process."""

import base64
import inspect
import io
import json
import logging
import os
import sys
from functools import wraps
from typing import TYPE_CHECKING, Any, get_args, get_type_hints

from bootstrap import ensure_dependencies, setup_environment

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from pymcp.registries.registry import ToolRegistry

_log = logging.getLogger("vision-tools")
_PREVIEW_EDGE = 1400
_PREVIEW_BYTES = 2_000_000


def _previews(paths: list[str], *, magnify: bool) -> list[dict[str, str]]:
    """Keep both registered views at the same scale within the inline PNG budget."""
    from PIL import Image

    views = []
    for path in paths:
        with Image.open(path) as opened:
            scale = min(4 if magnify else 1, _PREVIEW_EDGE / max(opened.size))
            size = (max(1, round(opened.width * scale)), max(1, round(opened.height * scale)))
            views.append(
                opened.resize(
                    size, Image.Resampling.NEAREST if scale > 1 else Image.Resampling.LANCZOS
                )
            )
    while True:
        buffers = [io.BytesIO() for _ in views]
        for view, data in zip(views, buffers, strict=True):
            view.save(data, "PNG")
        if sum(data.tell() for data in buffers) <= _PREVIEW_BYTES:
            return [
                {
                    "type": "image",
                    "mimeType": "image/png",
                    "data": base64.b64encode(data.getbuffer()).decode("ascii"),
                }
                for data in buffers
            ]
        for view in views:
            view.thumbnail((max(1, view.width * 3 // 4), max(1, view.height * 3 // 4)))


def _tool_result(
    fn: Callable[..., Mapping[str, Any]], image_key: str | None = None
) -> Callable[..., dict[str, Any]]:
    @wraps(fn)
    def call(**kwargs: Any) -> dict[str, Any]:
        try:
            result = fn(**kwargs)
            content = [{"type": "text", "text": json.dumps(result)}]
            if image_key:
                paths = [result.get("grid_image") or result[image_key]]
                if "detail_image" in result:
                    paths.append(result["detail_image"])
                content.extend(
                    _previews(
                        paths, magnify=image_key == "output_path" and "grid_image" not in result
                    )
                )
            return {"content": content}
        except ValueError as exc:
            message = str(exc)
        except Exception:
            _log.exception("Tool %s failed", fn.__name__)
            message = f"Internal error in {fn.__name__}. Check logs."
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps({"error": message})}],
        }

    return call


def _input_schema(fn: Callable[..., object]) -> dict[str, Any]:
    """Expose named tool arguments, including defaults and unpacked display options."""
    from pydantic import TypeAdapter

    annotations = get_type_hints(fn)
    properties: dict[str, Any] = {}
    required = []
    for name, param in inspect.signature(fn).parameters.items():
        annotation = annotations[name]
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            options = get_args(annotation)[0]
            properties.update(TypeAdapter(options).json_schema()["properties"])
            continue
        properties[name] = TypeAdapter(annotation).json_schema()
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            properties[name]["default"] = param.default
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _start_server() -> None:
    from pymcp import CapabilitySettings, ServerSettings, create_app, run_stdio_server

    from tools.colors import extract_colors
    from tools.contrast import check_contrast
    from tools.crop import crop_image, image_info

    settings = ServerSettings(
        name="vision-tools",
        version="0.1.0",
        protocol_mode="dual",
        capabilities=CapabilitySettings(tasks_enabled=False),
    )
    app = create_app(server_settings=settings)
    registry: ToolRegistry = app.state.registry_manager.tool_registry

    def register(
        name: str, fn: Callable[..., Mapping[str, Any]], desc: str, image_key: str | None = None
    ) -> None:
        registry.register(_tool_result(fn, image_key), name=name, description=desc)
        definition = registry.get(name)
        assert definition is not None
        # The toolkit's inferred schemas omit defaults and union types. Publish the
        # complete Python call signature, including numeric bounds' optional inputs.
        definition.input_schema = _input_schema(fn)

    register(
        "get_image_coordinates_grid",
        image_info,
        "Inspect the screenshot on a labeled 0-1 grid. X increases rightward, Y downward. "
        "For exact bounds of a flat-colored element, pass measure_at=[x,y] inside its fill, "
        "clear of text or borders. Returns that connected fill's hex, size and source bounds. "
        "Other regions of the same color are excluded.",
        "grid_image",
    )
    register(
        "crop_to_magnify_image",
        crop_image,
        "Zoom into a screenshot using original normalized x1,y1,x2,y2. Padding is in source "
        "pixels (default 20). To measure a target, pass your best tight box, show_detail=true "
        "and padding=12 or more. Inspect the natural crop first. In the companion view pink "
        "marks YOUR proposed box. Cyan shows fine color changes. Gold marks tips of narrow "
        "features traced back across the boundary. The tool varies the proposed box and reports "
        "repeatable endpoints in traced_edges_px and traced_edges_normalized. For a feature "
        "attached to the target, use the reported normalized edge in your measurement, including "
        "faint extremities. Cross-check any competing background structure on the natural crop. "
        "Measure the unreported sides on the original pixel rulers. "
        "Use show_grid=true for natural colors alone. Top/left rulers read original pixel "
        "edges, bottom/right original normalized edges. Right and bottom are exclusive.",
        "output_path",
    )
    register(
        "extract_colors",
        extract_colors,
        "Find dominant colors in the original screenshot or normalized region. Each hex is "
        "an observed pixel color. Percentages describe the color group's share. Supply all four "
        "region coordinates or omit them. n_colors is 1-20.",
    )
    register(
        "check_contrast",
        check_contrast,
        "Check two six-digit sRGB hex colors against WCAG AA/AAA text contrast. Set "
        "text_is_large for 18pt regular or 14pt bold text. Includes RGB, HSL and OKLCH.",
    )
    # MCP uses UTF-8 on pipes, including Windows hosts with a legacy code page.
    for stream in (sys.stdin, sys.stdout):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    run_stdio_server(app)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    if "--setup" in sys.argv:
        setup_environment(dev="--dev" in sys.argv)
        return
    ensure_dependencies()
    _start_server()


if __name__ == "__main__":
    main()
