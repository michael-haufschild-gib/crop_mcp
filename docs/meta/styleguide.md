# Style Guide — Immutable Rules

Violations are code review rejections. No exceptions.

## Python Style

| Rule | Example |
|-|-|
| `from __future__ import annotations` | First import in every module |
| Type hints on all function signatures | `def foo(x: float) -> dict:` |
| Docstrings on all public functions | Google style (Args/Returns sections) |
| f-strings for formatting | `f"Got {val}"`, not `"Got %s" % val` |

## Import Order

1. `__future__` imports
2. Standard library (`os`, `sys`, `pathlib`)
3. Third-party (`PIL`, `numpy`, `mcp`)
4. Local (`from .validators import ...`, `from tools.crop import ...`)

Blank line between each group.

## Naming

| Entity | Convention | Example |
|-|-|-|
| Tool functions | `snake_case` | `crop_image`, `extract_colors` |
| Private helpers | `_leading_underscore` | `_kmeans`, `_draw_label_pill` |
| Public constants | `UPPER_SNAKE` | `SUPPORTED_EXTENSIONS`, `CYAN`, `YELLOW` |
| Private constants | `_UPPER_SNAKE` | `_GRID_DIR`, `_FONT_PATHS` |
| Module files | `snake_case.py` | `crop.py`, `colors.py`, `validators.py` |

## Error Handling

- Tool implementations raise `ValueError` with multi-line, helpful messages.
- Server wrappers catch all exceptions and return `{"error": "..."}` JSON.
- Never let exceptions propagate to MCP transport (kills the server).
- Never use `assert` for runtime validation — it can be stripped with `-O`.

## Return Values

- Tool implementation functions return `dict`.
- MCP-registered tool functions return `str` (JSON-serialized).
- Include enough context for the caller to take the next action (e.g., `output_path` so Claude can read the file).
