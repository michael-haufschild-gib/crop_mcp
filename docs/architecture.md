# Architecture Guide for LLM Coding Agents

**Purpose**: Instructions for adding tools, modifying existing ones, and navigating the codebase.
**Read This When**: Adding a new tool, modifying tool behavior, or changing server configuration.
**Stack**: Python 3.9+, FastMCP (stdio), Pillow, numpy

## File Placement

| Type | Location | Example |
|-|-|-|
| Shared validators & utilities | `tools/validators.py` | `validate_image_path`, `cleanup_temp_dir` |
| Tool implementation | `tools/{name}.py` | `tools/crop.py`, `tools/colors.py`, `tools/grid.py`, `tools/contrast.py` |
| MCP server wiring | `server.py` | Tool registration, transport config |
| Venv bootstrapping | `bootstrap.py` | Dependency checking, auto-setup, venv relaunching |
| Setup/install | `setup.sh` | Venv creation, dependency install |
| Tests | `tests/test_{name}.py` | `test_crop.py`, `test_colors.py`, `test_contrast.py` |
| Live QA images + checklist | `tests/generate_live_images.py`, `tests/live_qa_checklist.md` | Manual MCP testing procedure |

## Module Dependency Flow

```
bootstrap.py (stdlib only — no project dependencies)
server.py → bootstrap.py
          → tools/crop.py     → tools/grid.py → tools/validators.py
          → tools/colors.py   ─────────────→ tools/validators.py
          → tools/contrast.py (stdlib only — no tools/ dependencies)
```

No circular dependencies. `bootstrap.py` uses only stdlib. Image tool modules import validators from `tools/validators.py`. `tools/contrast.py` uses only stdlib (`math`, `re`).

## How to Add a New Tool

**Template** (`tools/new_tool.py`):

```python
"""tool_name tool — One-line description."""
from __future__ import annotations

from .validators import validate_image_path  # reuse shared validators

def tool_name(image_path: str, ...) -> dict:
    """Tool docstring.

    Args:
        image_path: Absolute path to the source image.

    Returns:
        Dict with result fields.
    """
    path = validate_image_path(image_path)
    # Implementation
    return {"key": "value"}
```

**Steps**:

1. Create `tools/{name}.py` with a function returning a `dict`.
2. Import shared validators from `tools.validators` (`validate_image_path`, `validate_coordinates`).
3. In `server.py`, import the function and register it with `@mcp.tool()`.
4. Wrap the call in try/except returning `json.dumps({"error": str(e)})` on failure.
5. Write a tool description optimized for Claude's tool selection (when to use, not just what it does).
6. Create `tests/test_{name}.py` with pytest tests.
7. Add test cases to `tests/live_qa_checklist.md` for MCP-level verification.
8. Run `make check` (or `bash lint.sh`) to verify all quality gates pass.

## Server Wiring Pattern

Every tool in `server.py` follows this exact structure:

```python
@mcp_server.tool(
    name="tool_name",
    description="When-to-use description for Claude's tool selector.",
)
def tool_name(param: str, ...) -> str:
    """Docstring with Args."""
    try:
        result = _tool_impl(param=param, ...)
        return json.dumps(result)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {e}"})
```

Key rules:
- Tool functions return `str` (JSON-serialized dict). Never raise — always catch and return error JSON.
- Implementation lives in `tools/`, not in `server.py`. The server only wires and serializes.
- Tool descriptions describe **when** to use the tool, not just what it does.

## Coordinate System

All tools use normalized 0-1 coordinates: `(0,0)` = top-left, `(1,1)` = bottom-right.

- Validate with `validate_coordinates(x1, y1, x2, y2)` from `tools.validators`.
- Convert to pixels: `px = int(normalized * dimension)`.
- Clamp padding to image bounds: `max(0, px - padding)`, `min(dim, px + padding)`.

## Shared Validators

Located in `tools/validators.py` (imported by all tool modules):

| Function | Purpose |
|-|-|
| `validate_image_path(path) -> Path` | Check file exists, is a supported image format |
| `validate_coordinates(x1, y1, x2, y2)` | Check 0-1 range, proper ordering |
| `cleanup_temp_dir(dir_path, max_mb)` | LRU eviction of oldest files when dir exceeds limit |
| `SUPPORTED_EXTENSIONS` | Set of valid image suffixes |

## Common Mistakes

- **Don't**: Add scipy or sklearn. **Do**: Use pure numpy (see `_kmeans` in `tools/colors.py`).
- **Don't**: Print to stdout (breaks stdio transport). **Do**: Use `logging` to stderr.
- **Don't**: Crash the MCP server on bad input. **Do**: Raise `ValueError` — the server wrapper catches it.
- **Don't**: Return raw dicts from MCP tool functions. **Do**: Return `json.dumps(result)`.
- **Don't**: Import validators from `tools/crop.py`. **Do**: Import from `tools/validators.py`.

## On-Demand References

| Domain | Serena Memory |
|-|-|
| Full folder map, key files | `crop-mcp/codebase-structure` |
| Python style, naming | `crop-mcp/code-style-conventions` |
