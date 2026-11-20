# Vision Tools MCP architecture

The host starts one Python process and communicates over stdio. PyMCP Kit handles protocol negotiation, tool discovery and calls. The server registers four tool names. It sends logs to stderr. [MCP stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

## Where to make a change

| Change | Owning code |
|---|---|
| Interpreter selection, dependency checks and checkout setup | [Bootstrap](../bootstrap.py) and [executable entry point](../server.py). See [ADR-002](adr/002-reuse-installed-python.md). |
| Public tool names, schemas and preview encoding | [Server registration](../server.py). The [stdio host](../stdio_host.py) handles session notifications and cancellation. |
| Screenshot geometry | [Crop and image info](../tools/crop.py) use [validators](../tools/validators.py) for source coordinates, [rulers](../tools/grid.py) for display, [fill measurement](../tools/measure.py) for exact connected bounds and [edge detail](../tools/edge_detail.py) for candidate tips. |
| Color analysis or accessibility | [Palette extraction](../tools/colors.py) operates on image pixels. [Contrast](../tools/contrast.py) takes two hex values and requires no image slot. |
| Result lifetime or concurrency | [Image runtime](../tools/runtime.py) owns the session and its files. [OS file locks](../file_lock.py) coordinate independent processes. See [ADR-003](adr/003-session-owned-images.md). |

## Tool contract

Inputs use normalized coordinates. Pixel boxes include their left and top edges and exclude their right and bottom edges. The crop metadata includes both the exact pixel edges and those edges divided by the original dimensions. A normalized edge obtained from a pixel box can be passed back to the crop tool.

Implementations return typed dictionaries. The server puts the JSON representation in the first MCP text block. Grid and crop add an MCP image block, while retaining full-resolution crop and annotated-grid paths for filesystem callers. For invalid image inputs, the tool returns a JSON error and sets the MCP error flag. Unexpected exceptions go to stderr and the client receives a short diagnostic. [MCP tool result examples](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#tool-result)

### Changing a public image tool

1. Give the Python operation a typed signature with the defaults callers should see. Name its source argument `image_path` so the adapter holds the image slot through inline encoding.
2. Decorate the public image function with `@image_request()` so direct Python calls receive the same resource protection. Validate the path and open it with `open_image` to apply the decode limit and EXIF orientation.
3. Use `pixel_edge` to convert normalized edges to original pixels. For example, on a 200 × 100 image, the box `(0, 0, 0.5, 1)` with zero padding covers columns 0–99 and all 100 rows.
4. Return source measurements in a typed dictionary. Save generated PNGs through `save_png` and caller-selected exports through `export_png`.
5. Register the public name and description in `_start_server`. Supply the image key when the response includes a preview. The adapter derives the published input schema from the function signature, including defaults and unpacked crop options.
6. Check both the Python result and the real MCP response. Verify the advertised arguments, metadata and inline image agree. [Testing guide](testing.md#writing-a-tool-test)

### Reading a detail crop

When a caller requests `show_detail`, the crop returns two inline PNGs with identical source rulers. The first shows natural colors. The second draws the proposed box over a grayscale crop. Cyan highlights local changes in red-minus-green and blue-minus-green along the horizontal and vertical axes. The previews share a display scale and total byte budget. [Detail rendering](../tools/edge_detail.py)

On crops up to 1200 source pixels per side, the server looks for runs of color detail above the surrounding noise level. It follows a possible tip across a proposed edge using texture or a narrow stroke that contrasts with both flanks. It repeats the measurement with the rectangle expanded and contracted by three source pixels. A gold circle marks a tip found in at least two of the three measurements. `edge_checks_px` gives those source pixel locations. When a side has one such tip, `traced_edges_px` and `traced_edges_normalized` give its half-open edge in both coordinate systems. A background feature can also cross a proposed box. The natural crop lets the caller check which object owns the feature.

## Process and file lifetime

The host owns its stdio process. The transport sleeps until it has input or an outbound message. A stateless connection can serve calls without starting a stateful outbound queue. Closing the input pipe finishes the server. On Unix, SIGTERM also releases the session's files even when the input pipe is still open.

PyMCP Kit 0.3.0 checks every 10 ms for its first stateful session and keeps cancellation events for completed request IDs. The stdio adapter gates the queue on an event and releases each request's SDK cancellation manager at completion. When upgrading PyMCP Kit, verify both protocol modes and queued cancellation. [Stdio tests](../tests/test_server.py) · [Lifecycle tests](../tests/test_cleanup.py)

Image calls acquire one local worker slot and one OS file lock shared by processes using the same per-user cache. Each acquisition waits up to ten seconds. The lock covers decode, rendering, temporary-file retention and inline encoding. Contrast checks bypass both slots. Cancelled waiters check their request state before starting work. Cancellation also stops ongoing palette iterations and flood-fill scans, and is checked before publishing an export. A Pillow operation already in progress can finish before control returns to Python.

The runtime uses `vision-tools-v1` under macOS `~/Library/Caches`, Windows `%LOCALAPPDATA%`, or Linux `$XDG_CACHE_HOME` (default `~/.cache`). An absolute `VISION_TOOLS_CACHE_DIR` overrides the cache location. The runtime root retains two empty lock files. Keeping their names stable prevents a new process from opening a different lock while an older process still holds the original. Each session that writes files creates a private directory and holds a separate OS lock for its lifetime. Startup cleanup tests that lock before touching a session. A process death releases it even if Python never runs a shutdown handler. A file held open by an external viewer on Windows can defer removal until the viewer closes and a server starts again. [Unix file locks](https://docs.python.org/3/library/fcntl.html#fcntl.flock) · [Windows file locks](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking)

A result set groups the raw crop and its companion views. Each session retains up to 50 MiB and 64 sets. The session accounts for the completed write, evicts older sets first and rolls back a failed call's temporary files. An explicit export uses a uniquely named staging file on the destination volume and an atomic replacement. The session records the staging name before encoding, so crash recovery can remove that exact file without touching the destination or scanning its directory.

Images are limited to 24 million source pixels before decode. Fill measurement uses a byte mask and traverses horizontal runs. Palette analysis counts small palettes exactly, then samples at most 200 × 200 pixels for clustering. Clustering keeps one nearest distance per sample. NumPy loads on demand for clustering or edge detail. See [ADR-001 and its implementation note](adr/001-keep-custom-kmeans.md#implementation-note-2026-11-20). The inline PNGs from one response share a 2,000,000-byte encoding budget. [Pillow image loading](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open)

## Optional local Serena notes

The linked sources work in a fresh checkout. A checkout with Serena configured may also have these local examples.

| Memory | Example |
|---|---|
| `codebase_structure` | Trace a shifted crop ruler from the original box through the canvas and inline preview. |
| `code_style_conventions` | Assert a tool error through the stdio client and read a returned PNG within the session. |
