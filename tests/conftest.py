"""Shared test fixtures for vision-tools MCP tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from tools import runtime

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _isolate_image_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep generated images and LRU eviction inside this test's workspace."""
    owner = runtime.ImageRuntime(tmp_path / "runtime")
    monkeypatch.setattr(runtime, "runtime", owner)
    try:
        yield
    finally:
        owner.close()


@pytest.fixture
def synthetic_image(tmp_path: Path) -> Path:
    """200x100 image: left half red, right half blue. Same as server.py self-test."""
    img = Image.new("RGB", (200, 100))
    img.paste(Image.new("RGB", (100, 100), (255, 0, 0)), (0, 0))
    img.paste(Image.new("RGB", (100, 100), (0, 0, 255)), (100, 0))
    path = tmp_path / "synthetic.png"
    img.save(str(path))
    return path


@pytest.fixture
def solid_color_image(tmp_path: Path) -> Callable[[tuple[int, int, int], tuple[int, int]], Path]:
    """Factory fixture: creates a solid-color image of given color and size."""
    _counter = [0]

    def _make(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> Path:
        img = Image.new("RGB", size, color)
        _counter[0] += 1
        path = tmp_path / f"solid_{_counter[0]}.png"
        img.save(str(path))
        return path

    return _make
