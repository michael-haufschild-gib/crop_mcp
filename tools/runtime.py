"""Bound simultaneous image work and own the files returned by a stdio session."""

from __future__ import annotations

import atexit
import json
import logging
import os
import re
import stat
import sys
import threading
import uuid
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from file_lock import LockTimeoutError, exclusive, try_lock

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import BinaryIO, Literal

    from PIL import Image


_MAX_BYTES = 50 * 1024**2
_MAX_BATCHES = 64
_WAIT_SECONDS = 10
_SESSION = re.compile(r"session-[0-9a-f]{32}")
_BATCH = re.compile(r"result-[0-9a-f]{32}")
_FILES = ("crop.png", "grid.png", "detail.png")
_log = logging.getLogger(__name__)
request_stopped: ContextVar[threading.Event | None] = ContextVar("request_stopped", default=None)


def _directory(path: Path) -> bool:
    return not path.is_symlink() and not path.is_junction() and path.is_dir()


def _stage_path(parent: Path, batch: Path) -> Path:
    return parent / f".vision-export-{batch.name}.tmp"


def _clear_stage(batch: Path) -> None:
    """Recover only this result's randomly named export stage, including on another volume."""
    marker = batch / ".export-parent"
    if marker.is_file() and not marker.is_symlink():
        parent = Path(json.loads(marker.read_text(encoding="ascii")))
        if parent.is_absolute():
            _stage_path(parent, batch).unlink(missing_ok=True)
        marker.unlink()
    (batch / ".export-intent").unlink(missing_ok=True)


def _discard_batch(path: Path) -> bool:
    """Keep foreign entries and externally locked files for a later cleanup."""
    try:
        if _directory(path):
            _clear_stage(path)
            for name in _FILES:
                (path / name).unlink(missing_ok=True)
            path.rmdir()
    except (OSError, ValueError):
        return False
    return not path.exists()


def _discard_session(path: Path) -> None:
    for batch in path.iterdir():
        if _BATCH.fullmatch(batch.name):
            _discard_batch(batch)
    # Keep the ownership marker if, for example, an external viewer holds a PNG open.
    if all(item.name == ".owner" for item in path.iterdir()):
        (path / ".owner").unlink(missing_ok=True)
        path.rmdir()


class ImageRuntime:
    """One process owns a session. Each successful image call retains one result set."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.session: Path | None = None
        self.owner: BinaryIO | None = None
        self.history: deque[tuple[Path, int]] = deque()
        self.local = threading.local()
        self.active = threading.Lock()
        self.closed = False

    def _check_root(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not _directory(self.root):
            raise ValueError(f"Expected a private temporary directory at {self.root}")
        if sys.platform != "win32":
            info = self.root.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError(f"Expected an owner-only temporary directory at {self.root}")

    def reap(self) -> None:
        """Remove abandoned results, even on a contrast-only client's next startup."""
        if not self.root.exists():
            return
        self._check_root()
        with exclusive(self.root / ".sessions.lock", _WAIT_SECONDS):
            for path in self.root.iterdir():
                if _SESSION.fullmatch(path.name) and _directory(path):
                    self._reap_one(path)

    @staticmethod
    def _reap_one(path: Path) -> None:
        marker = path / ".owner"
        try:
            if not marker.exists():
                path.rmdir()  # Interrupted between creating the directory and taking ownership.
                return
            if not marker.is_file() or marker.is_symlink():
                return
            with marker.open("r+b") as handle:
                if not try_lock(handle):
                    return
            _discard_session(path)
        except OSError as exc:
            _log.debug("Deferred cleanup of %s: %s", path, exc)

    def _session_dir(self) -> Path:
        if self.session is None:
            with exclusive(self.root / ".sessions.lock", _WAIT_SECONDS):
                path = self.root / f"session-{uuid.uuid4().hex}"
                path.mkdir(mode=0o700)
                handle = (path / ".owner").open("x+b")
                try:
                    if not try_lock(handle):
                        raise RuntimeError("Could not claim a new image session")
                except BaseException:
                    handle.close()
                    raise
                self.owner, self.session = handle, path
        return self.session

    def batch_dir(self) -> Path:
        """Create storage only for a request that writes a file."""
        if self.local.batch is None:
            self.local.batch = self._session_dir() / f"result-{uuid.uuid4().hex}"
            self.local.batch.mkdir()
        return Path(self.local.batch)

    def _retain(self, batch: Path) -> None:
        size = sum(path.stat().st_size for path in batch.iterdir())
        if size == 0:
            batch.rmdir()
            return
        if size > _MAX_BYTES:
            raise ValueError("Temporary result exceeds 50 MiB. Use output_path or a smaller crop.")
        total = size + sum(size for _, size in self.history)
        for _ in range(len(self.history)):
            if total <= _MAX_BYTES and len(self.history) < _MAX_BATCHES:
                break
            path, old_size = self.history.popleft()
            if _discard_batch(path):
                total -= old_size
            else:
                self.history.append((path, old_size))
        if total > _MAX_BYTES or len(self.history) >= _MAX_BATCHES:
            raise ValueError("Temporary results are in use. Close open PNGs and retry.")
        self.history.append((batch, size))

    def check_active(self) -> None:
        stopped = request_stopped.get()
        if self.closed or (stopped is not None and stopped.is_set()):
            raise ValueError("The image request has been cancelled or its session is closing.")

    @contextmanager
    def request(self) -> Iterator[None]:
        """Hold the image slot through saving, inline encoding and retention."""
        if hasattr(self.local, "batch"):
            yield
            return
        if not self.active.acquire(timeout=_WAIT_SECONDS):
            raise ValueError("This session is processing another image. Retry shortly.")
        try:
            self.check_active()
            self._check_root()
            with exclusive(
                self.root / ".images.lock", _WAIT_SECONDS, check_active=self.check_active
            ):
                self.check_active()
                self.local.batch = None
                try:
                    yield
                    self.check_active()
                    if self.local.batch is not None:
                        self._retain(self.local.batch)
                except BaseException:
                    if self.local.batch is not None:
                        _discard_batch(self.local.batch)
                    raise
                finally:
                    del self.local.batch
        except LockTimeoutError as exc:
            raise ValueError("Another session is processing an image. Retry shortly.") from exc
        finally:
            self.active.release()

    def close(self) -> None:
        """Wait for the current writer and release this session's generated files."""
        self.closed = True
        with self.active:
            if self.session is None or self.owner is None:
                return
            try:
                with exclusive(self.root / ".sessions.lock", _WAIT_SECONDS):
                    self.owner.close()
                    _discard_session(self.session)
            except OSError as exc:
                _log.warning("Deferred cleanup of %s: %s", self.session, exc)
            finally:
                self.owner.close()
                self.session = None
                self.owner = None
                self.history.clear()


def _cache_root() -> Path:
    """Choose the same directory for GUI and shell hosts with different TMPDIRs."""
    override = os.environ.get("VISION_TOOLS_CACHE_DIR")
    if override:
        cache = Path(override).expanduser()
        if not cache.is_absolute():
            raise ValueError("VISION_TOOLS_CACHE_DIR must be an absolute directory.")
    elif sys.platform == "darwin":
        cache = Path.home() / "Library" / "Caches"
    elif os.name == "nt":
        cache = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        xdg = Path(os.environ.get("XDG_CACHE_HOME", ""))
        cache = xdg if xdg.is_absolute() else Path.home() / ".cache"
    return cache.resolve() / "vision-tools-v1"


runtime = ImageRuntime(_cache_root())
atexit.register(runtime.close)


def check_active() -> None:
    """Let long-running image calculations stop when the host cancels."""
    runtime.check_active()


@contextmanager
def image_request() -> Iterator[None]:
    """Group nested calls, including previews, into one resource reservation."""
    with runtime.request():
        yield


def save_png(image: Image.Image, kind: Literal["crop", "grid", "detail"]) -> Path:
    """Save a generated image under the session's retention policy."""
    with image_request():
        runtime.check_active()
        path = runtime.batch_dir() / f"{kind}.png"
        image.save(path, "PNG")
        return path


def export_png(image: Image.Image, path: Path) -> None:
    """Publish only complete PNGs. User-selected exports survive session shutdown."""
    if path.is_relative_to(runtime.root):
        raise ValueError("Choose an output_path outside the Vision Tools temporary directory.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with image_request():
        batch = runtime.batch_dir()
        staged = _stage_path(path.parent, batch)
        # Publish the intent before writing outside the session. A hard kill at
        # any later point can leave only this uniquely named stage to collect.
        intent = batch / ".export-intent"
        intent.write_text(json.dumps(str(path.parent)), encoding="ascii")
        marker = intent.replace(batch / ".export-parent")
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            handle = os.fdopen(os.open(staged, flags, 0o600), "wb")
        except FileExistsError:
            marker.unlink()
            raise
        try:
            with handle:
                image.save(handle, "PNG")
            if path.is_file():
                staged.chmod(stat.S_IMODE(path.stat().st_mode) & 0o777)
            runtime.check_active()
            staged.replace(path)
        finally:
            _clear_stage(batch)
