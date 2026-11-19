"""Blind, counterbalanced screenshot measurement with identical input pixels in every arm."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tests.composite_geometry import EDGE_TOLERANCE, read_scenes, render, resolution_argument

TOOLS = ("get_image_coordinates_grid", "crop_to_magnify_image")


def host_options(root: Path, script: Path) -> list[str]:
    config = {
        "command": json.dumps(sys.executable),
        "args": json.dumps([str(script)]),
        "enabled_tools": json.dumps(TOOLS),
        "env": "{"
        + ", ".join(f"{k}={json.dumps(str(root))}" for k in ("TMPDIR", "TEMP", "TMP"))
        + "}",
        **{f"tools.{tool}.approval_mode": '"approve"' for tool in TOOLS},
    }
    return [
        arg
        for name, value in config.items()
        for arg in ("-c", f"mcp_servers.vision-tools.{name}={value}")
    ]


def cold_run(
    work: Path, description: str, model: str, server: Path | None
) -> tuple[list[float], list[dict[str, Any]]]:
    schema = work.parent / "response-schema.json"
    shape = {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}
    schema.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"box": shape},
                "required": ["box"],
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    output = work.parent / "answer.json"
    output.unlink(missing_ok=True)
    prompt = (
        f"The attached image shows the original screenshot at {work / 'scene.png'}. "
        f"Estimate the complete outside bounds of {description}. "
        "Include visible antialiased edges, lettering and attached details. Exclude empty space. "
        "Return [left,top,right,bottom] as fractions of the ORIGINAL width and height. "
        "Top left is (0,0); right and bottom are exclusive. Pixel accuracy matters. "
        "Use the screenshot and any registered screenshot grid/crop tools available. "
        "Do not use shell, code, other files, external sources, or other tools."
    )
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Install the Codex CLI to run the cold evaluation.")
    disabled = ("apps", "plugins", "shell_tool", "view_image", "image_generation", "memories")
    args = [
        codex,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-s",
        "read-only",
        *(arg for feature in disabled for arg in ("--disable", feature)),
        "-m",
        model,
        "-c",
        'model_reasoning_effort="medium"',
        "-C",
        str(work),
        "--json",
        "--output-schema",
        str(schema),
        "-o",
        str(output),
    ]
    if server is not None:
        args.extend(host_options(work.parent, server))
    args.extend(["-i", str(work / "scene.png"), "--", prompt])
    calls: list[dict[str, Any]] = []
    inputs = {(work / "scene.png").resolve()}
    with subprocess.Popen(
        args, stdout=subprocess.PIPE, text=True, encoding="utf-8", stdin=subprocess.DEVNULL
    ) as proc:
        if proc.stdout is None:
            raise RuntimeError("Codex did not open its event stream.")
        for line in proc.stdout:
            event = json.loads(line)
            item = event.get("item", {})
            if event.get("type") != "item.completed":
                continue
            _record_action(item, calls, inputs, server is not None)
        if proc.wait():
            raise RuntimeError("Codex did not finish the trial.")
    result: dict[str, list[float]] = json.loads(output.read_text(encoding="utf-8"))
    return result["box"], calls


def _record_action(
    item: dict[str, Any], calls: list[dict[str, Any]], inputs: set[Path], assisted: bool
) -> None:
    kind = item.get("type")
    if kind in {"agent_message", "reasoning", "todo_list", "plan_update"}:
        return
    if kind != "mcp_tool_call":
        raise RuntimeError(f"Unassigned action in blind trial: {kind}")
    if not assisted or item.get("server") != "vision-tools" or item.get("tool") not in TOOLS:
        raise RuntimeError(f"Unassigned MCP call: {item.get('server')}/{item.get('tool')}")
    arguments = dict(item.get("arguments") or {})
    source = Path(arguments.pop("image_path")).resolve()
    if source not in inputs:
        raise RuntimeError(f"Model inspected an image outside its assigned inputs: {source.name}")
    for block in (item.get("result") or {}).get("content", []):
        if block.get("type") == "text":
            metadata = json.loads(block["text"])
            inputs.update(
                Path(metadata[k]).resolve()
                for k in ("grid_image", "output_path", "detail_image")
                if k in metadata
            )
    arguments.pop("output_path", None)
    calls.append(
        {
            "tool": item["tool"],
            "arguments": arguments,
            "status": item.get("status"),
            "error": bool(item.get("error") or (item.get("result") or {}).get("isError")),
        }
    )


def score(predicted: list[float], key: dict[str, Any]) -> dict[str, Any]:
    dimensions = (*key["size"], *key["size"])
    observed = [round(v * d) for v, d in zip(predicted, dimensions, strict=True)]
    offsets = [a - b for a, b in zip(observed, key["box"], strict=True)]
    return {
        "expected_px": key["box"],
        "predicted_px": observed,
        "predicted_normalized": predicted,
        "expected_xywh_normalized": key["xywh_normalized"],
        "edge_error_px": offsets,
        "xywh_error_px": [*offsets[:2], offsets[2] - offsets[0], offsets[3] - offsets[1]],
        "pass": max(map(abs, offsets)) <= EDGE_TOLERANCE,
        "exact": not any(offsets),
    }


def main() -> None:
    scenes = read_scenes()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6.2-astra")
    parser.add_argument("--scene", choices=scenes)
    parser.add_argument("--split", choices=("development", "holdout"))
    resolution_argument(parser, default=2)
    parser.add_argument(
        "--reference-server", type=Path, help="Add a frozen pre-change server as a third arm."
    )
    parser.add_argument("--arms", nargs="+", choices=("unaided", "reference", "aided"))
    args = parser.parse_args()
    servers = {"unaided": None, "aided": Path(__file__).resolve().parents[1] / "server.py"}
    if args.reference_server:
        servers["reference"] = args.reference_server.resolve(strict=True)
    arms = args.arms or list(servers)
    if set(arms) - servers.keys():
        parser.error("The reference arm requires --reference-server.")
    for idx, (scene, definition) in enumerate(scenes.items()):
        if (args.scene and scene != args.scene) or (
            args.split and definition["split"] != args.split
        ):
            continue
        with TemporaryDirectory(prefix="vision-blind-") as tmp:
            root = Path(tmp).resolve()
            work = root / "input"
            key = render(scene, definition, work / "scene.png", args.density)
            for arm in arms[idx % len(arms) :] + arms[: idx % len(arms)]:
                predicted, calls = cold_run(
                    work, definition["description"], args.model, servers[arm]
                )
                result = {
                    "scene": scene,
                    "arm": arm,
                    "model": args.model,
                    "density": args.density,
                    "size": key["size"],
                    "sha256": key["sha256"],
                    "calls": calls,
                    **score(predicted, key),
                }
                sys.stdout.write(json.dumps(result) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    main()
