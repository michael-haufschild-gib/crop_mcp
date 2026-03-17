"""Shared test fixtures for vision-tools MCP tests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from PIL import Image


@pytest.fixture()  # type: ignore[untyped-decorator]
def synthetic_image(tmp_path: Path) -> Path:
    """200x100 image: left half red, right half blue. Same as server.py self-test."""
    img = Image.new("RGB", (200, 100))
    img.paste(Image.new("RGB", (100, 100), (255, 0, 0)), (0, 0))
    img.paste(Image.new("RGB", (100, 100), (0, 0, 255)), (100, 0))
    path = tmp_path / "synthetic.png"
    img.save(str(path))
    return path


@pytest.fixture()  # type: ignore[untyped-decorator]
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
