# Vision Tools MCP

An MCP server that gives Claude Code four image analysis tools for inspecting screenshots, extracting colors, and checking accessibility.

## Tools

| Tool | Purpose |
|-|-|
| `get_image_coordinates_grid` | Returns image dimensions and a coordinate-reference grid overlay with labeled gridlines (.1 through .9) for planning crops. |
| `crop_to_magnify_image` | Crops a region using normalized 0-1 coordinates. Acts as a magnifying glass for reading text or verifying visual details. |
| `extract_colors` | Extracts dominant colors as exact hex values using k-means clustering. Optionally analyzes a subregion. |
| `check_contrast` | Computes WCAG 2.1 contrast ratio between two hex colors. Returns AA/AAA pass/fail and HSL/OKLCH conversions. |

## Prerequisites

- Python 3.9+
- macOS, Linux, or WSL

### Runtime dependencies

| Package | Version |
|-|-|
| mcp[cli] | >=1.0, <3 |
| Pillow | >=10, <12 |
| numpy | >=1.24, <3 |

## Setup

```bash
bash setup.sh
```

This creates a virtualenv at `~/.vision-tools-env/` and installs all dependencies (runtime and dev).

### Register with Claude Code

```bash
claude mcp add --transport stdio --scope user vision-tools \
  -- ~/.vision-tools-env/bin/python3 /absolute/path/to/server.py
```

### Awareness Rule

For Claude to proactively use these tools (not just when explicitly asked), copy the awareness rule:

```bash
cp .claude/rules/vision-tools-awareness.md ~/.claude/rules/
```

## Development

All commands assume setup has been run (`bash setup.sh`).

| Command | Purpose |
|-|-|
| `make check` | Run full quality pipeline (lint + format + typecheck + test + file length) |
| `make test` | Run pytest suite only |
| `make lint` | Run ruff check only |
| `make format` | Auto-format all Python files |
| `make typecheck` | Run mypy in strict mode |
| `make smoke-test` | Quick self-test without pytest |
| `make clean` | Remove caches and build artifacts |

### Environment variables

| Variable | Default | Purpose |
|-|-|-|
| `LOG_LEVEL` | `INFO` | Server log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Or use the underlying tools directly:

```bash
~/.vision-tools-env/bin/pytest -v
~/.vision-tools-env/bin/ruff check .
~/.vision-tools-env/bin/mypy .
bash lint.sh                    # all of the above in sequence
```

## Architecture

```
server.py             MCP server entry point — tool registration, venv auto-setup, self-test
tools/
  validators.py       Shared validators: validate_image_path, validate_coordinates, cleanup_temp_dir
  crop.py             crop_image and image_info implementations
  grid.py             Coordinate grid overlay rendering
  colors.py           extract_colors with numpy k-means clustering
  contrast.py         WCAG contrast ratio, HSL/OKLCH conversion (stdlib only)
tests/
  conftest.py         Shared fixtures: synthetic_image, solid_color_image
  test_validators.py  Tests for path and coordinate validation
  test_crop.py        Tests for crop_image and image_info
  test_grid.py        Pixel-level grid rendering tests
  test_colors.py      Tests for _kmeans and extract_colors
  test_cleanup.py     Tests for LRU temp directory eviction
  test_validate_region.py  Tests for optional region coordinate validation
  test_server.py      Server wrapper contract tests (JSON serialization, error handling)
  test_integration.py End-to-end pipeline tests (info → crop → colors)
```

### Dependency Flow

```
server.py → tools/crop.py     → tools/grid.py → tools/validators.py
          → tools/colors.py   ─────────────→ tools/validators.py
          → tools/contrast.py (stdlib only — no tools/ dependencies)
```

No circular dependencies. All tools depend on `validators.py` for shared validation. Grid rendering is isolated from crop logic.

### Coordinate System

All tools use normalized 0-1 coordinates: `(0, 0)` = top-left, `(1, 1)` = bottom-right. Conversion to pixels: `px = int(normalized * dimension)`. Padding is clamped to image bounds.

### Adding a New Tool

1. Create `tools/{name}.py` with a function returning a `dict`.
2. Import shared validators from `tools.validators`.
3. In `server.py`, register with `@mcp.tool()` — wrap in try/except, return `json.dumps(result)`.
4. Add tests in `tests/test_{name}.py`.
5. Run `make check` to verify.

See `docs/architecture.md` for the full pattern template.

## Quality Standards

- **Linter**: ruff with 20+ rule groups (pyflakes, bugbear, complexity, naming, etc.)
- **Formatter**: ruff format (double quotes, 100 char line length)
- **Type checker**: mypy in strict mode
- **Tests**: pytest with synthetic image fixtures — no real screenshots in automated tests
- **Complexity**: Max cyclomatic complexity 10, max 40 statements per function
- **File length**: Max 750 lines per Python file
- **CI**: GitHub Actions runs lint + format + typecheck + test on push and PR
