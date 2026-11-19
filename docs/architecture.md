# Vision Tools MCP architecture

The host starts one Python process and communicates over stdio. PyMCP Kit handles protocol negotiation, tool discovery and calls. The server registers four tool names. It sends logs to stderr. [MCP stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

| File | Responsibility |
|---|---|
| `server.py` | Register tool descriptions and schemas from their Python signatures. Serialize results and encode bounded inline PNG previews. |
| `bootstrap.py` | Select an installed Python, check the runtime dependency versions, and prepare a checkout-local virtual environment when needed. Setup prints the absolute launch paths for local stdio clients. |
| `file_lock.py` | Hold cross-process locks on Unix and Windows with a bounded wait. |
| `stdio_host.py` | Wake the outbound queue when a stateful session starts and retain cancellation state only for active requests. |
| `tools/runtime.py` | Admit image work, own result files, and reclaim abandoned sessions and export stages. |
| `tools/crop.py` | Validate requested bounds, clamp padding, save the raw crop, return the actual source region. |
| `tools/grid.py` | Overlay a normalized grid on the full image. On zoomed crops, draw original pixel and normalized rulers in the margins. |
| `tools/edge_detail.py` | Highlight fine color changes and locate possible protrusions in the padding of a proposed box. |
| `tools/measure.py` | Find the four-connected component at a point with exactly matching RGBA values and return its half-open bounding box. |
| `tools/colors.py` | Count an exact small palette or cluster sampled source pixels and return a representative observed shade per cluster. |
| `tools/contrast.py` | Convert sRGB, HSL and OKLCH and evaluate WCAG text thresholds using the unrounded ratio. |
| `tools/validators.py` | Validate paths and coordinates, convert normalized edges to source pixels, and reject oversized image headers before decoding. |

## Tool contract

Inputs use normalized coordinates. Pixel boxes include their left and top edges and exclude their right and bottom edges. The crop metadata includes both the exact pixel edges and those edges divided by the original dimensions. A normalized edge obtained from a pixel box can be passed back to the crop tool.

Implementations return typed dictionaries. The server puts the JSON representation in the first MCP text block. Grid and crop add an MCP image block, while retaining full-resolution crop and annotated-grid paths for filesystem callers. For invalid image inputs, the tool returns a JSON error and sets the MCP error flag. Unexpected exceptions go to stderr and the client receives a short diagnostic. [MCP tool result examples](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#tool-result)

Implement image operations in `tools/` and keep the transport boundary in `server.py`. Changes to a public tool must work through a real stdio call. [Testing guide](testing.md)

When a caller requests `show_detail`, the crop returns two inline PNGs with identical source rulers. The first shows natural colors. The second draws the proposed box over a grayscale crop. Cyan highlights local changes in red-minus-green and blue-minus-green along the horizontal and vertical axes. The previews share a display scale and total byte budget. [Image gradients](https://docs.opencv.org/4.13.0/d5/d0f/tutorial_py_gradients.html)

On crops up to 1200 source pixels per side, the server looks for runs of color detail above the surrounding noise level. It follows a possible tip across a proposed edge using texture or a narrow stroke that contrasts with both flanks. It repeats the measurement with the rectangle expanded and contracted by three source pixels. A gold circle marks a tip found in at least two of the three measurements. `edge_checks_px` gives those source pixel locations. When a side has one such tip, `traced_edges_px` and `traced_edges_normalized` give its half-open edge in both coordinate systems. A background feature can also cross a proposed box. The natural crop lets the caller check which object owns the feature.

## Process and file lifetime

The host owns its stdio process. The transport sleeps until it has input or an outbound message. A stateless connection can serve calls without starting a stateful outbound queue. Closing the input pipe finishes the server. On Unix, SIGTERM also releases the session's files even when the input pipe is still open.

PyMCP Kit 0.3.0 checks every 10 ms for its first stateful session and keeps cancellation events for completed request IDs. The stdio adapter gates the queue on an event and releases each request's SDK cancellation manager at completion. When upgrading PyMCP Kit, verify both protocol modes and queued cancellation. [Stdio tests](../tests/test_server.py) · [Lifecycle tests](../tests/test_cleanup.py)

Image calls acquire one local worker slot and one OS file lock shared by processes using the same per-user cache. Each acquisition waits up to ten seconds. The lock covers decode, rendering, temporary-file retention and inline encoding. Contrast checks bypass both slots. Cancelled waiters check their request state before starting work. Cancellation also stops ongoing palette iterations and flood-fill scans, and is checked before publishing an export. A Pillow operation already in progress can finish before control returns to Python.

The runtime uses `vision-tools-v1` under macOS `~/Library/Caches`, Windows `%LOCALAPPDATA%`, or Linux `$XDG_CACHE_HOME` (default `~/.cache`). An absolute `VISION_TOOLS_CACHE_DIR` overrides the cache location. The runtime root retains two empty lock files. Keeping their names stable prevents a new process from opening a different lock while an older process still holds the original. Each session that writes files creates a private directory and holds a separate OS lock for its lifetime. Startup cleanup tests that lock before touching a session. A process death releases it even if Python never runs a shutdown handler. A file held open by an external viewer on Windows can defer removal until the viewer closes and a server starts again. [Unix file locks](https://docs.python.org/3/library/fcntl.html#fcntl.flock) · [Windows file locks](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking)

A result set groups the raw crop and its companion views. The session accounts for the completed write, evicts older sets first and rolls back a failed call's temporary files. An explicit export uses a uniquely named staging file on the destination volume and an atomic replacement. The session records the staging name before encoding, so crash recovery can remove that exact file without touching the destination or scanning its directory.

Images are limited to 24 million source pixels before decode. Fill measurement uses a byte mask and traverses horizontal runs. Palette analysis counts small palettes exactly, then samples at most 200 × 200 pixels for clustering. Clustering keeps one nearest distance per sample. NumPy loads only for clustering or edge detail. The inline PNGs from one response share a 2,000,000-byte encoding budget. [Pillow image loading](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open)
