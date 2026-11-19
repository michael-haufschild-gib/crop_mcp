"""Exercise the checkout through the same JSON-RPC pipes as an MCP host."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_SERVER = Path(__file__).resolve().parents[1] / "server.py"


class StdioClient:
    """A single sequential MCP session with bounded reads and correlated replies."""

    def __init__(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdin is not None
        assert proc.stdout is not None
        self.writer = proc.stdin
        self.reader = proc.stdout
        self.proc = proc
        self.killed = False
        self.request_id = 0

    async def kill(self, *, terminate: bool = False) -> None:
        """Simulate losing a host without running the server's shutdown hooks."""
        if terminate:
            self.proc.terminate()
        else:
            self.proc.kill()
        self.killed = True
        await asyncio.wait_for(self.proc.wait(), timeout=5)

    async def _send(self, message: dict[str, Any]) -> None:
        self.writer.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
        await self.writer.drain()

    async def begin_request(self, method: str, **params: Any) -> int:
        """Write a request, allowing a test to cancel it while the image slot is busy."""
        self.request_id += 1
        await self._send(
            {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        )
        return self.request_id

    async def cancel(self, request_id: int) -> None:
        await self._send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": request_id},
            }
        )

    async def request(self, method: str, **params: Any) -> dict[str, Any]:
        """Send one request and verify the matching response envelope."""
        request_id = await self.begin_request(method, **params)
        line = await asyncio.wait_for(self.reader.readline(), timeout=20)
        response = json.loads(line)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == request_id
        assert "error" not in response, response
        return cast("dict[str, Any]", response["result"])

    async def initialize(self) -> None:
        """Negotiate the protocol before exposing tools to a test."""
        hello = await self.request(
            "initialize",
            protocolVersion="2025-11-25",
            capabilities={},
            clientInfo={"name": "test", "version": "1"},
        )
        assert hello["serverInfo"]["name"] == "vision-tools"
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def call(self, name: str, **arguments: Any) -> dict[str, Any]:
        """Call a tool by its public MCP name."""
        return await self.request("tools/call", name=name, arguments=arguments)


@asynccontextmanager
async def stdio_client(
    workspace: Path, *, initialize: bool = True, cache: Path | None = None
) -> AsyncIterator[StdioClient]:
    """Start outside the checkout and require a clean exit when the host closes stdin."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(_SERVER),
        cwd=workspace,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        env={
            **os.environ,
            "PYTHONIOENCODING": "ascii",
            "VISION_TOOLS_CACHE_DIR": str(cache or workspace),
            "TMPDIR": str(workspace),
            "TEMP": str(workspace),
            "TMP": str(workspace),
        },
        limit=4_000_000,
    )
    client = StdioClient(proc)
    try:
        if initialize:
            await client.initialize()
        yield client
    finally:
        if proc.stdin is not None:
            proc.stdin.close()
        try:
            status = await asyncio.wait_for(proc.wait(), timeout=5)
            if client.killed:
                assert status != 0
            else:
                assert status == 0
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise
