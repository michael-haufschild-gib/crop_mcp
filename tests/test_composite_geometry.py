"""Verify the scorer against the finished single-target image and the pristine background."""

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from tests.cold_geometry import score
from tests.composite_geometry import ASSETS, Resolution, backdrop, read_scenes, render, scene_scale
from tools.crop import crop_image


def test_exact_foreground_footprints(tmp_path: Path) -> None:
    for scene in read_scenes():
        for density in (1, 2):
            _verify_footprint(scene, density, tmp_path)
    _verify_footprint("rally", "5k", tmp_path)


def _verify_footprint(scene: str, density: Resolution, tmp_path: Path) -> None:
    definition = read_scenes()[scene]
    path = tmp_path / "scene.png"
    key = render(scene, definition, path, density)
    with Image.open(ASSETS / scene / "foreground.png") as source:
        alpha = source.getchannel("A").getbbox()
        assert alpha is not None
        assert 0 < alpha[0] < alpha[2] < source.width
        assert 0 < alpha[1] < alpha[3] < source.height
    scale = scene_scale(scene, density)
    with Image.open(path) as finished, backdrop(scene, scale) as pristine:
        observed = ImageChops.difference(finished, pristine).getbbox()
        assert observed is not None
        assert observed == key["box"], (scene, density)
        x, y, r, b = observed
        w, h = finished.size
        assert [x, y] == [round(coord * scale) for coord in definition["at"]]
        if density == "5k":
            assert w <= 5120
            assert h <= 2880
            assert w == 5120 or h == 2880
        assert key["xywh_normalized"] == (x / w, y / h, (r - x) / w, (b - y) / h)
        fractions = [x / w, y / h, r / w, b / h]
        assert score(fractions, key)["exact"] is True
        crop = crop_image(
            str(path), x / w, y / h, r / w, b / h, str(tmp_path / "crop.png"), padding=0
        )
        with Image.open(crop["output_path"]) as cutout:
            assert cutout.tobytes() == finished.crop(observed).tobytes()


def test_traces_recover_the_native_extremities_in_the_original_misses(tmp_path: Path) -> None:
    # Start from the boxes reported in the first native blind run, using only each composite.
    for scene, (left, top, right, bottom) in {
        "ruins": (722, 630, 802, 688),
        "station": (1031, 360, 1148, 427),
    }.items():
        path = tmp_path / f"{scene}.png"
        key = render(scene, read_scenes()[scene], path)
        w, h = key["size"]
        result = crop_image(
            str(path),
            left / w,
            top / h,
            right / w,
            bottom / h,
            str(tmp_path / "crop.png"),
            padding=16,
            show_detail=True,
        )
        assert result["traced_edges_px"]["top"] == key["box"][1]
        assert result["traced_edges_normalized"]["top"] == key["box"][1] / h
        if scene == "ruins":
            assert result["traced_edges_px"]["bottom"] == key["box"][3]
            assert result["traced_edges_normalized"]["bottom"] == key["box"][3] / h
        else:
            assert result["edge_checks_px"]["top"] == [(1071, 352)]


def test_each_edge_and_size_error_are_scored() -> None:
    key: dict[str, Any] = {
        "size": (100, 80),
        "box": (15, 16, 40, 48),
        "xywh_normalized": (0.15, 0.20, 0.25, 0.40),
    }
    assert score([0.17, 0.20, 0.40, 0.60], key)["pass"] is True
    result = score([0.18, 0.20, 0.40, 0.60], key)
    assert result["pass"] is False
    assert result["xywh_error_px"] == [3, 0, -3, 0]
