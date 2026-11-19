"""Start the toolkit's outbound queue only when this host has a stateful session."""

from __future__ import annotations

import asyncio
import signal
import threading
from typing import TYPE_CHECKING, Any

from pymcp.tasks import CancellationManager
from pymcp.transport import StdioTransport

from tools.runtime import request_stopped, runtime

if TYPE_CHECKING:
    from types import FrameType

    from fastapi import FastAPI
    from pymcp.tasks.cancellation import CancellationCallback


class LiveRequests:
    """Scope the SDK cancellation state to pending requests on this stdio connection."""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[CancellationManager, threading.Event]] = {}

    def create_token(self, request_id: Any = None) -> str:
        manager = CancellationManager()
        token = manager.create_token(request_id)
        stopped = threading.Event()
        self._pending[token] = (manager, stopped)
        # The SDK copies this request's context to its image worker thread.
        request_stopped.set(stopped)
        return token

    def register_callback(self, token: str, callback: CancellationCallback) -> None:
        if pending := self._pending.get(token):
            pending[0].register_callback(token, callback)

    def cancel(self, token: str, reason: str | None = None) -> bool:
        if pending := self._pending.get(token):
            manager, stopped = pending
            stopped.set()
            return manager.cancel(token, reason)
        return False

    def is_cancelled(self, token: str) -> bool:
        pending = self._pending.get(token)
        return pending is not None and pending[0].is_cancelled(token)

    async def wait(self, token: str) -> bool:
        if pending := self._pending.get(token):
            return bool(await pending[0].wait(token))
        return False

    def clear(self, token: str) -> None:
        if pending := self._pending.pop(token, None):
            manager, stopped = pending
            stopped.set()
            manager.clear(token)
            if request_stopped.get() is stopped:
                request_stopped.set(None)


class HostTransport(StdioTransport):
    """A stateless or uninitialized host waits without periodic timer wakeups."""

    def __init__(self) -> None:
        super().__init__()
        self._ready = asyncio.Event()

    def _ensure_session(self, app: FastAPI) -> str:
        session_id = super()._ensure_session(app)
        self._ready.set()
        return session_id

    async def _pump_session_queue(self, app: FastAPI) -> None:
        await self._ready.wait()
        await super()._pump_session_queue(app)


def _terminate(signum: int, _frame: FrameType | None) -> None:
    # The stdio reader can be blocked in another thread with its input pipe open.
    # Restore normal signal termination after releasing this process's files.
    signal.signal(signum, signal.SIG_DFL)
    try:
        runtime.close()
    finally:
        signal.raise_signal(signum)


def serve(app: FastAPI) -> None:
    """Run the host on stdio until its input pipe closes."""
    app.state.cancellation_manager = LiveRequests()
    previous = signal.signal(signal.SIGTERM, _terminate)
    try:
        asyncio.run(HostTransport().run(app))
    finally:
        signal.signal(signal.SIGTERM, previous)
