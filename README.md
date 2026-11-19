# Vision Tools MCP

Measure controls, icons and other elements in screenshots from Codex or another local MCP host. Image coordinates are fractions of the original screenshot's width and height. The top-left corner is `(0, 0)` and the bottom-right is `(1, 1)`.

| Tool | What the model gets |
|---|---|
| `get_image_coordinates_grid` | An inline image with coordinate rulers, original dimensions and pixels per percent. For a flat fill, pass `measure_at=[x,y]` inside it to get its exact connected pixel bounds and size. |
| `crop_to_magnify_image` | An inline zoom, a full-resolution PNG and the exact source bounds after padding. Set `show_grid=true` to see finer rulers in original coordinates. |
| `extract_colors` | Observed hex and RGB values for the dominant colors in an image or region. Small palettes are counted at full resolution. For richer images, the percentages estimate cluster coverage and each hex is the most frequent sampled shade in its cluster. Transparent images are composited on white, and the result identifies that background. |
| `check_contrast` | WCAG AA and AAA text verdicts from the unrounded luminance ratio of two sRGB hex colors, plus HSL and OKLCH values. |

## Measuring a screenshot

1. Use the grid on the original file to locate the target.
2. For a solid button, select a point on its fill, clear of lettering. The result includes `bounds_px` in left, top, right, bottom order. Right and bottom are exclusive. A border, shadow or gradient can extend beyond the selected fill.
3. To check a faint edge, pass your proposed box with `show_detail=true` and padding around it. The first image shows the natural crop. The second marks your box in pink and fine color changes in cyan. A gold circle marks a tip that crosses the outline and recurs when the tool moves the outline. Check that the feature belongs to the object. When a side has a single supported tip, read its source coordinate from `traced_edges_px` or its 0–1 coordinate from `traced_edges_normalized`. Both views have source pixel rulers on the top and left and normalized rulers on the bottom and right. Use `show_grid=true` for the natural image alone and `padding=0` to reproduce an exact box.

## Connect to Codex

Register this checkout once. With `uvx` available, the same registration works on macOS and Windows. Substitute the absolute path to this checkout, quoting it if it contains spaces.

```sh
codex mcp add vision-tools -- uvx --python 3.14 --from "/absolute/path/to/crop_mcp" vision-tools-mcp
```

The host starts the server and receives images over stdio. Existing registrations pointing to an installed Python interpreter and `server.py` also work. For Claude Code, use `claude mcp add --transport stdio --scope user vision-tools --` with the same `uvx` arguments.

## Development

The project targets Python 3.14+. Run `make setup` on macOS or Linux, or `py -3.14 server.py --setup --dev` on Windows, to install the locked development dependencies. On Unix, `make smoke-test` exercises the image pipeline and `make check` runs the quality checks. Set `LOG_LEVEL` to control stderr logging.

The testing guide includes the stdio contract checks and the blind screenshot evaluation. [Testing guide](docs/testing.md)
