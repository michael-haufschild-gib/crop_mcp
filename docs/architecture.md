# Architecture Guide for LLM Coding Agents

**Purpose**: Instructions for adding tools, modifying existing ones, and navigating the codebase.
**Read This When**: Adding a new tool, modifying tool behavior, or changing server configuration.
**Stack**: Python 3.9+, FastMCP (stdio), Pillow, numpy

## File Placement

| Type | Location | Example |
|-|-|-|
| Tool implementation | `tools/{name}.py` | `tools/crop.py`, `tools/colors.py` |
| MCP server wiring | `server.py` | Tool registration, transport config |
| Setup/install | `setup.sh` | Venv creation, dependency install |
| Test images | `tests/` | PNG files for manual/self-test |

## How to Add a New Tool

**Template** (`tools/new_tool.py`):

```python
"""tool_name tool — One-line description."""
from __future__ import annotations

from .crop import validate_image_path  # reuse shared validators

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
2. Import shared validators from `tools/crop.py` (`validate_image_path`, `validate_coordinates`).
3. In `server.py`, import the function and register it with `@mcp.tool()`.
4. Wrap the call in try/except returning `json.dumps({"error": str(e)})` on failure.
5. Write a tool description optimized for Claude's tool selection (when to use, not just what it does).
6. Add a test case to `_run_self_test()` in `server.py`.

## Server Wiring Pattern

Every tool in `server.py` follows this exact structure:

```python
@mcp.tool(
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

- Validate with `validate_coordinates(x1, y1, x2, y2)` from `tools/crop.py`.
- Convert to pixels: `px = int(normalized * dimension)`.
- Clamp padding to image bounds: `max(0, px - padding)`, `min(dim, px + padding)`.

## Shared Validators

Located in `tools/crop.py` (imported by other tools):

| Function | Purpose |
|-|-|
| `validate_image_path(path) -> Path` | Check file exists, is a supported image format |
| `validate_coordinates(x1, y1, x2, y2)` | Check 0-1 range, proper ordering |
| `SUPPORTED_EXTENSIONS` | Set of valid image suffixes |

## Common Mistakes

- **Don't**: Add scipy or sklearn. **Do**: Use pure numpy (see `_kmeans` in `tools/colors.py`).
- **Don't**: Print to stdout (breaks stdio transport). **Do**: Use `sys.stderr` for diagnostics.
- **Don't**: Crash the MCP server on bad input. **Do**: Raise `ValueError` — the server wrapper catches it.
- **Don't**: Return raw dicts from MCP tool functions. **Do**: Return `json.dumps(result)`.

## On-Demand References

| Domain | Serena Memory |
|-|-|
| Full folder map, key files | `crop-mcp/codebase-structure` |
| Python style, naming | `crop-mcp/code-style-conventions` |
