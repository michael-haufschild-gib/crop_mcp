"""Exclusive OS locks shared by setup and local MCP processes."""

from __future__ import annotations

import errno
import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path
    from typing import BinaryIO


class LockTimeoutError(TimeoutError):
    """A different writer held the resource for the entire wait budget."""


def try_lock(handle: BinaryIO) -> bool:
    """Lock byte zero until the handle closes, including after a process crash."""
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            raise
        return False
    return True


@contextmanager
def exclusive(
    path: Path, timeout: float, *, check_active: Callable[[], None] | None = None
) -> Iterator[None]:
    """Wait up to timeout seconds. A busy lock never starts a second worker."""
    with path.open("a+b") as handle:
        deadline = time.monotonic() + timeout
        delay = 0.025
        while not try_lock(handle):
            if check_active is not None:
                check_active()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LockTimeoutError(f"Timed out waiting for {path.name}")
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, 0.25)
        yield
