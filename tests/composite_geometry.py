"""Place one tightly trimmed foreground on one screenshot and record its measured bounds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageChops

ASSETS = Path(__file__).parent / "geometry_art"
EDGE_TOLERANCE = 2


def read_scenes() -> dict[str, Any]:
    return dict(json.loads((ASSETS / "scenes.json").read_text(encoding="utf-8")))


type Resolution = int | Literal["5k"]


def resolution_argument(parser: argparse.ArgumentParser, default: int) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--density", type=int, choices=(1, 2), default=default)
    group.add_argument(
        "--fit-5k",
        action="store_const",
        dest="density",
        const="5k",
        help="Fit the scene to 5120 by 2880 source pixels, preserving aspect ratio.",
    )


def scene_scale(scene: str, resolution: Resolution) -> float:
    if resolution == "5k":
        with Image.open(ASSETS / scene / "background.webp") as source:
            return min(5120 / source.width, 2880 / source.height)
    return resolution


def backdrop(scene: str, density: float) -> Image.Image:
    with Image.open(ASSETS / scene / "background.webp") as source:
        frame = source.convert("RGB")
    if density == 1:
        return frame
    size = (round(frame.width * density), round(frame.height * density))
    return frame.resize(size, Image.Resampling.LANCZOS)


def trimmed_foreground(scene: str, width: int) -> Image.Image:
    with Image.open(ASSETS / scene / "foreground.png") as source:
        bounds = source.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"Empty foreground: {scene}")
        art = source.crop(bounds)
    height = max(1, round(art.height * width / art.width))
    art = art.resize((width, height), Image.Resampling.LANCZOS)
    # Discard resampling fringes before placement. All retained pixels are in the scored image.
    art.putalpha(art.getchannel("A").point([a if a >= 16 else 0 for a in range(256)]))
    return art.crop(art.getchannel("A").getbbox())


def render(
    scene: str, definition: dict[str, Any], destination: Path, density: Resolution = 1
) -> dict[str, Any]:
    scale = scene_scale(scene, density)
    frame = backdrop(scene, scale)
    art = trimmed_foreground(scene, round(definition["width"] * scale))
    x, y = (round(n * scale) for n in definition["at"])
    box = (x, y, x + art.width, y + art.height)
    composite = frame.copy()
    composite.paste(art, (x, y), art.getchannel("A"))
    if ImageChops.difference(composite, frame).getbbox() != box:
        raise ValueError(f"{scene}: visible change disagrees with placement {box}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    composite.save(destination, "PNG")
    return {
        "size": frame.size,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "box": box,
        "xywh_normalized": (
            x / frame.width,
            y / frame.height,
            art.width / frame.width,
            art.height / frame.height,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    resolution_argument(parser, default=1)
    args = parser.parse_args()
    keys = {
        scene: render(scene, definition, args.destination / scene / "scene.png", args.density)
        for scene, definition in read_scenes().items()
    }
    (args.destination / "key.json").write_text(json.dumps(keys, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
