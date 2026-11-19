# Vision Tools MCP architecture

The host starts one Python process and communicates over stdio. PyMCP Kit handles protocol negotiation, tool discovery and calls. The server registers four tool names. It sends logs to stderr. [MCP stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

| File | Responsibility |
|---|---|
| `server.py` | Register tool descriptions and schemas from their Python signatures. Serialize results and encode bounded inline PNG previews. |
| `bootstrap.py` | Use an installed interpreter directly, or prepare the checkout environment for existing host registrations. |
| `tools/crop.py` | Validate requested bounds, clamp padding, save the raw crop, return the actual source region. |
| `tools/grid.py` | Overlay a normalized grid on the full image. On zoomed crops, draw original pixel and normalized rulers in the margins. |
| `tools/edge_detail.py` | Highlight fine color changes and locate possible protrusions in the padding of a proposed box. |
| `tools/measure.py` | Find the four-connected component at a point with exactly matching RGBA values and return its half-open bounding box. |
| `tools/colors.py` | Count an exact small palette or cluster sampled source pixels and return a representative observed shade per cluster. |
| `tools/contrast.py` | Convert sRGB, HSL and OKLCH and evaluate WCAG text thresholds using the unrounded ratio. |
| `tools/validators.py` | Validate paths and coordinates, convert normalized edges to source pixels, and evict old temporary images. |

## Tool contract

Inputs use normalized coordinates. Pixel boxes include their left and top edges and exclude their right and bottom edges. The crop metadata includes both the exact pixel edges and those edges divided by the original dimensions. A normalized edge obtained from a pixel box can be passed back to the crop tool.

Implementations return typed dictionaries. The server puts the JSON representation in the first MCP text block. Grid and crop add an MCP image block, while retaining full-resolution crop and annotated-grid paths for filesystem callers. For invalid image inputs, the tool returns a JSON error and sets the MCP error flag. Unexpected exceptions go to stderr and the client receives a short diagnostic. [MCP tool result examples](https://modelcontextprotocol.io/specification/2025-11-25/server/tools#tool-result)

Implement image operations in `tools/` and keep the transport boundary in `server.py`. Changes to a public tool must work through a real stdio call. [Testing guide](testing.md)

When a caller requests `show_detail`, the crop returns two inline PNGs with identical source rulers. The first shows natural colors. The second draws the proposed box over a grayscale crop. Cyan highlights local changes in red-minus-green and blue-minus-green along the horizontal and vertical axes. The previews share a display scale and total byte budget. [Image gradients](https://docs.opencv.org/4.13.0/d5/d0f/tutorial_py_gradients.html)

On crops up to 1200 source pixels per side, the server looks for runs of color detail above the surrounding noise level. It follows a possible tip across a proposed edge using texture or a narrow stroke that contrasts with both flanks. It repeats the measurement with the rectangle expanded and contracted by three source pixels. A gold circle marks a tip found in at least two of the three measurements. `edge_checks_px` gives those source pixel locations. When a side has one such tip, `traced_edges_px` and `traced_edges_normalized` give its half-open edge in both coordinate systems. A background feature can also cross a proposed box. The natural crop lets the caller check which object owns the feature.
