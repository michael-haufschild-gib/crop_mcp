# Vision Tools MCP

An MCP server that gives Claude Code two image tools: **crop_image** (zoom into screenshot regions) and **extract_colors** (get exact hex values from images).

## Setup

```bash
bash setup.sh
claude mcp add --transport stdio --scope user vision-tools -- ~/.vision-tools-env/bin/python3 /path/to/server.py
```

## Tools

**crop_image** — Crop a region using normalized 0-1 coordinates. Returns the saved crop path.

**extract_colors** — Extract dominant colors as hex values using k-means clustering. No more guessing colors from screenshots.

## Requirements

- Python 3.9+
- Dependencies installed automatically by `setup.sh`: `mcp`, `Pillow`, `numpy`
