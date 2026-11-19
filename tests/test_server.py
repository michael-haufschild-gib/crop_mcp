"""Exercise the protocol exactly as a stdio host sees it."""

import asyncio
import base64
import io
import json
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image

from server import _tool_result
from tests.stdio_client import StdioClient, stdio_client


async def _check_schemas(client: StdioClient) -> None:
    definitions = {
        tool["name"]: tool["inputSchema"] for tool in (await client.request("tools/list"))["tools"]
    }
    assert {name: set(schema["required"]) for name, schema in definitions.items()} == {
        "get_image_coordinates_grid": {"image_path"},
        "crop_to_magnify_image": {"image_path", "x1", "y1", "x2", "y2"},
        "extract_colors": {"image_path"},
        "check_contrast": {"foreground", "background"},
    }
    for schema in definitions.values():
        assert schema["additionalProperties"] is False
    assert definitions["crop_to_magnify_image"]["properties"]["padding"]["default"] == 20
    assert definitions["extract_colors"]["properties"]["n_colors"]["default"] == 6
    assert definitions["check_contrast"]["properties"]["text_is_large"]["default"] is False
    measure_types = definitions["get_image_coordinates_grid"]["properties"]["measure_at"]["anyOf"]
    assert {"type": "array", "items": {"type": "number"}} in measure_types
    assert definitions["crop_to_magnify_image"]["properties"]["x1"]["type"] == "number"
    assert definitions["crop_to_magnify_image"]["properties"]["show_grid"]["type"] == "boolean"
    assert definitions["crop_to_magnify_image"]["properties"]["show_detail"]["type"] == "boolean"


async def _check_detail_view(client: StdioClient, temp: Path) -> None:
    # The narrow top of the target has nearly the same brightness as the background.
    image = Image.new("RGB", (37, 41))
    for x in range(image.width):
        gray = 35 + x * 5
        image.paste((gray, gray, gray), (x, 0, x + 1, image.height))
    image.paste((120, 103, 80), (12, 16, 23, 27))
    image.paste((116, 108, 108), (16, 10, 17, 16))
    path = temp / "faint.png"
    image.save(path)
    result = await client.call(
        "crop_to_magnify_image",
        image_path=str(path),
        x1=12 / 37,
        y1=12 / 41,
        x2=23 / 37,
        y2=27 / 41,
        padding=20,
        show_detail=True,
    )
    metadata, natural, enhanced = result["content"]
    info = json.loads(metadata["text"])
    with (
        Image.open(info["output_path"]) as raw,
        Image.open(io.BytesIO(base64.b64decode(natural["data"]))) as first,
        Image.open(io.BytesIO(base64.b64decode(enhanced["data"]))) as second,
        Image.open(info["detail_image"]) as detail,
    ):
        assert raw.tobytes() == image.tobytes()
        assert first.size == second.size
        assert detail.tobytes() == second.tobytes()
        left, top = (first.width - 8 * image.width) // 2, (first.height - 8 * image.height) // 2
        tip = (left + 16 * 8, top + 10 * 8)
        above = (tip[0], tip[1] - 1)
        assert first.getpixel(tip) == (116, 108, 108, 255)
        assert first.getpixel(above) == (115, 115, 115, 255)
        assert second.getpixel((tip[0], top + 9 * 8)) == second.getpixel(above)
        assert second.getpixel((tip[0], top + 12 * 8 - 1)) == (255, 64, 143, 255)
        assert first.getpixel((tip[0], top + 12 * 8 - 1)) == (116, 108, 108, 255)
        # The thin stroke crosses the proposal. Its tip has greater local contrast.
        tip_color = cast("tuple[int, ...]", second.getpixel(tip))
        bg_color = cast("tuple[int, ...]", second.getpixel(above))
        assert sum(abs(a - b) for a, b in zip(tip_color, bg_color, strict=True)) > 30


async def _check_wire(image: Path, temp: Path) -> None:
    async with stdio_client(temp) as client:
        await _check_schemas(client)
        await _check_detail_view(client, temp)
        call = client.call

        grid = await call(
            "get_image_coordinates_grid", image_path=str(image), measure_at=[0.15, 0.5]
        )
        metadata, block = grid["content"]
        assert json.loads(metadata["text"])["measured_fill"]["bounds_px"] == [0, 0, 100, 100]
        with Image.open(io.BytesIO(base64.b64decode(block["data"]))) as preview:
            assert block["mimeType"] == "image/png"
            assert preview.size == (200, 100)
        crop = await call(
            "crop_to_magnify_image", image_path=str(image), x1=0.25, y1=0, x2=0.75, y2=1, padding=0
        )
        metadata, block = crop["content"]
        assert json.loads(metadata["text"])["width"] == 100
        with Image.open(io.BytesIO(base64.b64decode(block["data"]))) as preview:
            assert preview.size == (400, 400)
            assert preview.getpixel((199, 100)) == (255, 0, 0)
            assert preview.getpixel((200, 100)) == (0, 0, 255)
        ruled = await call(
            "crop_to_magnify_image",
            image_path=str(image),
            x1=0.25,
            y1=0,
            x2=0.75,
            y2=1,
            padding=0,
            show_grid=True,
        )
        metadata, block = ruled["content"]
        with (
            Image.open(json.loads(metadata["text"])["grid_image"]) as saved_grid,
            Image.open(io.BytesIO(base64.b64decode(block["data"]))) as inline,
        ):
            assert inline.tobytes() == saved_grid.tobytes()
        colors = await call("extract_colors", image_path=str(image), n_colors=2)
        assert {
            c["hex"]: c["percentage"] for c in json.loads(colors["content"][0]["text"])["colors"]
        } == {"#FF0000": 50, "#0000FF": 50}
        error = await call("get_image_coordinates_grid", image_path=str(temp / "missing.png"))
        assert error["isError"] is True
        assert "not found" in json.loads(error["content"][0]["text"])["error"]
        contrast = await call("check_contrast", foreground="#000000", background="#FFFFFF")
        assert json.loads(contrast["content"][0]["text"])["contrast_ratio"] == 21


@pytest.mark.integration
def test_host_lists_and_calls_every_tool(synthetic_image: Path, tmp_path: Path) -> None:
    asyncio.run(_check_wire(synthetic_image.rename(tmp_path / "visión-画面.png"), tmp_path))


def test_unexpected_failure_is_sanitized() -> None:
    def broken() -> dict[str, str]:
        raise RuntimeError("private implementation detail")

    response = _tool_result(broken)()
    assert response["isError"] is True
    assert (
        json.loads(response["content"][0]["text"])["error"]
        == "Internal error in broken. Check logs."
    )


@pytest.mark.integration
def test_stateless_client_can_call_without_initializing(tmp_path: Path) -> None:
    async def call() -> dict[str, Any]:
        async with stdio_client(tmp_path, initialize=False) as client:
            return await client.request(
                "tools/call",
                name="check_contrast",
                arguments={"foreground": "#000000", "background": "#FFFFFF"},
                _meta={
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {"name": "stateless", "version": "1"},
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            )

    result = asyncio.run(call())
    assert json.loads(result["content"][0]["text"])["contrast_ratio"] == 21
    assert list(tmp_path.glob("vision-tools-*")) == []


def test_finished_requests_release_cancellation_state_and_late_waiters() -> None:
    import threading
    import weakref

    from stdio_host import LiveRequests
    from tools.runtime import request_stopped

    manager = LiveRequests()
    workers: weakref.WeakSet[threading.Event] = weakref.WeakSet()
    for request_id in range(128):
        token = manager.create_token(request_id)
        stopped = request_stopped.get()
        if stopped is None:
            pytest.fail("The worker did not receive its request cancellation event")
        assert not stopped.is_set()
        workers.add(stopped)
        manager.clear(token)
        assert stopped.is_set()
        del stopped
    assert len(workers) == 0
    assert asyncio.run(manager.wait("127")) is False
    assert manager.cancel("127") is False
