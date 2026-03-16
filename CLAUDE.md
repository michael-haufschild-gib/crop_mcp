# Vision Tools MCP

MCP server providing `crop_image` and `extract_colors` tools for Claude Code.

## Setup

```bash
bash setup.sh
```

This creates a virtualenv at `~/.vision-tools-env/` and installs dependencies (mcp, Pillow, numpy).

## Run

The server runs automatically when Claude Code starts (configured in `~/.claude.json`).

Manual test: `~/.vision-tools-env/bin/python3 server.py --test`

## Architecture

- `server.py` — MCP server entry point (FastMCP, stdio transport)
- `tools/crop.py` — `crop_image` implementation
- `tools/colors.py` — `extract_colors` implementation (numpy k-means, no sklearn)
- `setup.sh` — Venv creation + dependency install (safe to re-run)

## Coordinate System

Both tools use normalized 0-1 coordinates: (0,0) = top-left, (1,1) = bottom-right.
