# Vision Tools MCP

Measure controls, icons and other elements in screenshots with any local MCP client that supports stdio. Image coordinates are fractions of the original screenshot's width and height. The top-left corner is `(0, 0)` and the bottom-right is `(1, 1)`.

| Tool | What the model gets |
|---|---|
| `get_image_coordinates_grid` | An inline image with coordinate rulers, original dimensions and pixels per percent. For a flat fill, pass `measure_at=[x,y]` inside it to get its exact connected pixel bounds and size. |
| `crop_to_magnify_image` | An inline zoom, a full-resolution PNG and the exact source bounds after padding. Set `show_grid=true` to see finer rulers in original coordinates. |
| `extract_colors` | Observed hex and RGB values for the dominant colors in an image or region. Small palettes are counted at full resolution. For richer images, the percentages estimate cluster coverage and each hex is the most frequent sampled shade in its cluster. Transparent images are composited on white, and the result identifies that background. |
| `check_contrast` | WCAG AA and AAA text verdicts from the unrounded luminance ratio of two sRGB hex colors, plus HSL and OKLCH values. |

## Set up once

Download and extract the [repository](https://github.com/michael-haufschild-gib/crop_mcp), or clone it with Git. Keep the folder where you want the MCP to run. Open a terminal in the folder containing `server.py`.

**macOS or Linux**

```sh
python3 server.py --setup
```

**Windows PowerShell**

```powershell
py -3 server.py --setup
```

If your Python command is `python`, use `python server.py --setup`. Setup uses an installed **Python 3.12 or newer**. If your default is Python 3.8–3.11, setup looks for a compatible interpreter. You can also run the command with the full path to your preferred Python. If you need to install Python, get it from [python.org](https://www.python.org/downloads/).

When the chosen Python already has compatible packages, setup uses it directly. Otherwise it installs the locked dependencies into `.vision-tools-env` inside this checkout. The first installation needs internet access and a writable checkout. Once setup finishes, it prints two registration commands and a JSON block with the actual paths for your machine. Use the output for your client below.

### Claude Code

Run the printed `claude mcp add --transport stdio --scope user vision-tools -- …` command in your terminal. This makes the tools available across your projects. Start Claude Code and enter `/mcp` to check the connection. [Claude Code MCP guide](https://code.claude.com/docs/en/mcp)

### Claude Desktop

1. Open **Settings → Developer → Edit Config** in the desktop app.
2. Paste the printed JSON into an empty configuration. If the file already has an `mcpServers` object, add just the `vision-tools` entry inside it and keep your other entries.
3. Save the file, fully quit Claude Desktop, and reopen it. Check **Settings → Developer** for the server status. [Claude Desktop local server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

### Google Antigravity

1. In **Antigravity IDE**, open **… → MCP Servers → Manage MCP Servers → View raw config** in the agent side panel. In the **Antigravity App**, open **Customizations → Installed → MCP Servers**, choose **Copy Config File Path**, and open that file in a text editor.
2. Paste the JSON printed by setup. If `mcpServers` already exists, merge the `vision-tools` entry into it.
3. Save and restart Antigravity. Find `vision-tools` in the MCP server list. Antigravity CLI also reads the same JSON from `.agents/mcp_config.json` in a workspace. Enter `/mcp` in the CLI to check its status. [Google Antigravity MCP guide](https://antigravity.google/docs/mcp)

### Codex

Run the printed `codex mcp add vision-tools -- …` command in your terminal. Run `codex mcp get vision-tools` to see the saved command and arguments. Start a new Codex session to use the tools.

For desktop setup without the CLI, open **Settings → MCP servers → Add server**. Name it `vision-tools`, choose **STDIO**, and copy the Python path from the printed JSON into **Command**. Add the `server.py` path as the single argument. Save and restart the server. The CLI, desktop app and IDE extension share configuration on the same host. [Codex MCP guide](https://developers.openai.com/codex/mcp/)

### Verify the connection

Ask your client **“Use the vision-tools `check_contrast` tool on black (#000000) text against white (#FFFFFF).”** Look for a tool call and a **21:1** contrast ratio. For screenshot tools, supply the absolute path to an image on the machine running the server.

If your client reports a missing executable or script after moving the checkout, rerun setup in the new location and update the registration with the paths it prints. If installation fails, rerun setup in a terminal to see the package installer’s error.

### Existing uvx installations

If you already manage MCP servers with `uvx`, you can keep that workflow. For example, this Codex registration lets uv select an installed compatible interpreter. Replace the quoted checkout path with yours.

```sh
codex mcp add vision-tools -- uvx --no-python-downloads --python ">=3.12" --from "/absolute/path/to/crop_mcp" vision-tools-mcp
```

## Running several clients

Each Claude, Codex or Antigravity session starts its own stdio server. Sessions in the same user account take turns processing images so simultaneous screenshots fit in memory. Contrast checks can run while another session processes an image. If an image call reports that the server is busy, retry it. Each input can contain up to 24 million pixels, including a 5120 × 2880 screenshot.

Generated crops, grids and detail images belong to the session that returned them. The server keeps the newest complete results within 50 MiB and 64 result sets per session, and removes them when the session closes. To keep a crop, pass an absolute `output_path` outside the server's temporary directory. For grids or detail views, copy the returned PNG while the session is open. If two calls export to the same path, the last completed export wins.

After a forced stop, the next server launch using the same cache removes abandoned results and interrupted export files. The server uses your account’s cache directory even when clients have different temporary directories. To use another disk, set `VISION_TOOLS_CACHE_DIR` to the same absolute folder in each client. The installed Python environment stays available for the next launch. A first-time installer can finish if the client that started it disconnects. Other clients wait for that installer.

## Measuring a screenshot

1. Use the grid on the original file to locate the target.
2. For a solid button, select a point on its fill, clear of lettering. The result includes `bounds_px` in left, top, right, bottom order. Right and bottom are exclusive. A border, shadow or gradient can extend beyond the selected fill.
3. To check a faint edge, pass your proposed box with `show_detail=true` and padding around it. The first image shows the natural crop. The second marks your box in pink and fine color changes in cyan. A gold circle marks a tip that crosses the outline and recurs when the tool moves the outline. Check that the feature belongs to the object. When a side has a single supported tip, read its source coordinate from `traced_edges_px` or its 0–1 coordinate from `traced_edges_normalized`. Both views have source pixel rulers on the top and left and normalized rulers on the bottom and right. Use `show_grid=true` for the natural image alone and `padding=0` to reproduce an exact box.

## Development

Run `make setup` on macOS or Linux, or `py -3 server.py --setup --dev` on Windows, to install the locked development dependencies. On Unix, `make lint` checks the code and test assertions. Use `make unit-test` for unit tests and `make smoke-test` for the image pipeline and live stdio protocol. CI runs the full `make check` gate. Set `LOG_LEVEL` to control stderr logging.

The testing guide includes the stdio contract checks and the blind screenshot evaluation. [Testing guide](docs/testing.md)
