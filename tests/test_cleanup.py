"""Retention, partial failure and process ownership of image results."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from file_lock import exclusive
from tests.stdio_client import stdio_client
from tools import runtime
from tools.crop import crop_image, image_info

if TYPE_CHECKING:
    from typing import BinaryIO

    from tests.stdio_client import StdioClient


def test_evicts_whole_old_result_and_preserves_latest_views(
    synthetic_image: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "_MAX_BATCHES", 1)
    first = image_info(str(synthetic_image))
    latest = crop_image(str(synthetic_image), 0, 0, 1, 1, show_detail=True)
    assert not Path(first["grid_image"]).exists()
    for path in (latest["grid_image"], latest["detail_image"], latest["output_path"]):
        with Image.open(path) as view:
            assert view.format == "PNG"


def test_byte_limit_accounts_for_new_write_and_rolls_back_an_oversize_call(
    synthetic_image: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = str(synthetic_image)
    first = Path(crop_image(path, 0, 0, 1, 1)["output_path"])
    monkeypatch.setattr(runtime, "_MAX_BYTES", first.stat().st_size)
    second = Path(crop_image(path, 0, 0, 1, 1)["output_path"])
    assert not first.exists()
    with pytest.raises(ValueError, match="smaller crop"):
        crop_image(path, 0, 0, 1, 1, show_grid=True)
    assert list(second.parent.parent.glob("*/*.png")) == [second]


def test_held_file_is_retried_and_never_counted_as_reclaimed(
    synthetic_image: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = str(synthetic_image)
    first = Path(crop_image(path, 0, 0, 1, 1)["output_path"])
    monkeypatch.setattr(runtime, "_MAX_BYTES", first.stat().st_size)
    unlink = Path.unlink

    def when_closed(file: Path, *, missing_ok: bool = False) -> None:
        if file == first:
            raise PermissionError("file is open")
        unlink(file, missing_ok=missing_ok)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", when_closed)
        with pytest.raises(ValueError, match="in use"):
            crop_image(path, 0, 0, 1, 1)
    assert list(first.parent.parent.glob("*/*.png")) == [first]
    replacement = Path(crop_image(path, 0, 0, 1, 1)["output_path"])
    assert replacement.exists()
    assert not first.exists()


def test_export_failure_preserves_previous_contents(
    synthetic_image: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "my-export.png"
    target.write_bytes(b"previous contents")

    def interrupted(_image: Image.Image, handle: BinaryIO, _fmt: str) -> None:
        handle.write(b"partial PNG")
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", interrupted)
    with pytest.raises(OSError, match="disk full"):
        crop_image(str(synthetic_image), 0, 0, 1, 1, output_path=str(target))
    assert target.read_bytes() == b"previous contents"
    assert list(tmp_path.glob(".vision-export-*")) == []


def test_busy_image_slot_releases_after_holder_exits(
    synthetic_image: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.contrast import check_contrast

    monkeypatch.setattr(runtime, "_WAIT_SECONDS", 0)
    root = runtime.runtime.root
    root.mkdir(mode=0o700)
    with exclusive(root / ".images.lock", 0):
        with pytest.raises(ValueError, match="Retry"):
            image_info(str(synthetic_image))
        assert check_contrast("#000000", "#FFFFFF")["contrast_ratio"] == 21
        assert list(root.glob("session-*")) == []
    assert Path(image_info(str(synthetic_image))["grid_image"]).exists()


async def _grid(client: StdioClient, path: Path) -> Path:
    result = await client.call("get_image_coordinates_grid", image_path=str(path))
    assert "isError" not in result or result["isError"] is False, result
    return Path(json.loads(result["content"][0]["text"])["grid_image"])


async def _sessions(path: Path, other_tmp: Path) -> None:
    async with stdio_client(path.parent) as survivor:
        async with stdio_client(other_tmp, cache=path.parent) as other:
            kept, temporary = await asyncio.gather(_grid(survivor, path), _grid(other, path))
            export = path.parent / "saved.png"
            await other.call(
                "crop_to_magnify_image",
                image_path=str(path),
                x1=0,
                y1=0,
                x2=1,
                y2=1,
                output_path=str(export),
            )
            assert kept.parent.parent != temporary.parent.parent
        assert not temporary.parent.parent.exists()
        with Image.open(export) as saved:
            assert saved.getpixel((0, 0)) == (255, 0, 0)
        async with stdio_client(other_tmp, cache=path.parent) as crashed:
            abandoned = await _grid(crashed, kept)
            await crashed.kill()
        assert abandoned.is_file()
        async with stdio_client(path.parent):
            assert not abandoned.parent.parent.exists()
            assert kept.is_file()
        assert (await _grid(survivor, kept)).is_file()
    assert not kept.parent.parent.exists()
    assert await asyncio.to_thread(path.is_file)
    assert await asyncio.to_thread(export.is_file)


@pytest.mark.integration
def test_parallel_hosts_disconnect_and_recover_a_killed_session(synthetic_image: Path) -> None:
    other_tmp = synthetic_image.parent / "other-host-tmp"
    other_tmp.mkdir()
    asyncio.run(_sessions(synthetic_image, other_tmp))


def test_death_during_export_reclaims_staging_file_without_touching_user_export(
    synthetic_image: Path, tmp_path: Path
) -> None:
    import subprocess
    import sys

    root = tmp_path / "crash-runtime"
    target = tmp_path / "export.png"
    target.write_bytes(b"complete previous image")
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os, sys
from pathlib import Path
from PIL import Image
from tools import runtime
from tools.crop import crop_image
runtime.runtime = runtime.ImageRuntime(Path(sys.argv[1]))
def interrupt(image, handle, fmt):
    handle.write(b"partial image")
    handle.flush()
    os._exit(27)
Image.Image.save = interrupt
crop_image(sys.argv[2], 0, 0, 1, 1, output_path=sys.argv[3])
""",
            str(root),
            str(synthetic_image),
            str(target),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )
    assert process.returncode == 27
    assert len(list(tmp_path.glob(".vision-export-*.tmp"))) == 1
    runtime.ImageRuntime(root).reap()
    assert list(tmp_path.glob(".vision-export-*.tmp")) == []
    assert list(root.glob("session-*")) == []
    assert target.read_bytes() == b"complete previous image"


async def _cancel_export(path: Path, target: Path) -> None:
    async with stdio_client(path.parent) as client:
        grid = await _grid(client, path)
        with exclusive(grid.parents[2] / ".images.lock", 0):
            request = await client.begin_request(
                "tools/call",
                name="crop_to_magnify_image",
                arguments={
                    "image_path": str(path),
                    "x1": 0,
                    "x2": 1,
                    "y1": 0,
                    "y2": 1,
                    "output_path": str(target),
                },
            )
            contrast = await client.call(
                "check_contrast", foreground="#000000", background="#FFFFFF"
            )
            assert json.loads(contrast["content"][0]["text"])["contrast_ratio"] == 21
            await client.cancel(request)
            await client.request("ping")
        assert (await _grid(client, path)).is_file()


@pytest.mark.integration
def test_cancelled_queued_export_leaves_destination_intact(synthetic_image: Path) -> None:
    target = synthetic_image.parent / "export.png"
    target.write_bytes(b"existing export")
    asyncio.run(_cancel_export(synthetic_image, target))
    assert target.read_bytes() == b"existing export"


@pytest.mark.skipif(os.name != "posix", reason="Windows TerminateProcess uses crash recovery")
@pytest.mark.integration
def test_sigterm_cleans_images_while_the_host_pipe_remains_open(synthetic_image: Path) -> None:
    async def terminate() -> Path:
        async with stdio_client(synthetic_image.parent) as client:
            png = await _grid(client, synthetic_image)
            await client.kill(terminate=True)
            return png

    result = asyncio.run(terminate())
    assert not result.parent.parent.exists()
    assert synthetic_image.is_file()


def test_default_runtime_is_shared_across_host_temporary_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VISION_TOOLS_CACHE_DIR", raising=False)
    first = runtime._cache_root()
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    assert runtime._cache_root() == first
    monkeypatch.setenv("VISION_TOOLS_CACHE_DIR", str(tmp_path))
    assert runtime._cache_root() == tmp_path.resolve() / "vision-tools-v1"


def test_caller_cannot_overwrite_a_managed_result(synthetic_image: Path) -> None:
    png = Path(image_info(str(synthetic_image))["grid_image"])
    previous = png.read_bytes()
    with pytest.raises(ValueError, match="outside"):
        crop_image(str(synthetic_image), 0, 0, 1, 1, output_path=str(png))
    assert png.read_bytes() == previous


@pytest.mark.skipif(os.name != "posix", reason="Creating Windows symlinks needs extra privileges")
def test_recovery_preserves_unrelated_files_and_never_follows_a_session_symlink(
    tmp_path: Path,
) -> None:
    root = runtime.runtime.root
    root.mkdir(mode=0o700)
    elsewhere = tmp_path / "other-app"
    bundle = elsewhere / f"result-{'1' * 32}"
    bundle.mkdir(parents=True)
    (elsewhere / ".owner").touch()
    (bundle / "crop.png").write_bytes(b"other application")
    (root / f"session-{'2' * 32}").symlink_to(elsewhere, target_is_directory=True)
    other = root / "user-note.txt"
    other.write_text("keep")
    runtime.runtime.reap()
    assert (bundle / "crop.png").read_bytes() == b"other application"
    assert other.read_text() == "keep"
