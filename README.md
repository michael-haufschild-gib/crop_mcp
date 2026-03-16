# Vision Tools MCP

An MCP server that gives Claude Code two image tools: **crop_image** (zoom into screenshot regions) and **extract_colors** (get exact hex values from images).

## Setup

```bash
bash setup.sh
claude mcp add --transport stdio --scope user vision-tools -- ~/.vision-tools-env/bin/python3 /path/to/server.py
```

## Tools

**crop_to_magnify_image** — Crop a region using normalized 0-1 coordinates to magnify and inspect details. Returns the saved crop path.

**extract_colors** — Extract dominant colors as hex values using k-means clustering. No more guessing colors from screenshots.

## Awareness Rule

For Claude to proactively use these tools (not just when explicitly asked), copy the awareness rule into your global Claude Code rules:

```bash
cp .claude/rules/vision-tools-awareness.md ~/.claude/rules/
```

This plants a lightweight reminder — Claude will remember the tools exist when analyzing screenshots, without being forced to use them every time.

## Requirements

- Python 3.9+
- Dependencies installed automatically by `setup.sh`: `mcp`, `Pillow`, `numpy`
