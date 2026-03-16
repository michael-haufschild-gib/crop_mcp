# Vision Tools MCP

MCP server providing `image_info`, `crop_image`, and `extract_colors` tools for Claude Code.

## Constraints

| Constraint | Rule |
|-|-|
| No stdout | Never print to stdout — breaks stdio transport. Use `sys.stderr`. |
| No heavy deps | numpy only for math. No scipy, sklearn, or torch. |
| Never crash | Tool functions catch all exceptions and return error JSON. |
| 0-1 coordinates | All coordinates normalized. `(0,0)` = top-left, `(1,1)` = bottom-right. |
| Lint clean | All code must pass `bash lint.sh` before commit. Zero warnings. |
| Max 750 lines | No Python file may exceed 750 lines. Split into modules. |
| Max complexity 10 | No function may exceed McCabe complexity 10 or 40 statements. |

## Required Reading

@docs/architecture.md
@docs/testing.md
@docs/meta/styleguide.md

## Commands

| Command | Purpose |
|-|-|
| `bash setup.sh` | Create venv + install deps (safe to re-run) |
| `bash lint.sh` | Lint + format check + file length check |
| `~/.vision-tools-env/bin/ruff check --fix .` | Auto-fix lint violations |
| `~/.vision-tools-env/bin/ruff format .` | Auto-format all files |
| `~/.vision-tools-env/bin/python3 server.py --test` | Self-test all tools |
| `~/.vision-tools-env/bin/python3 server.py` | Start MCP server (stdio) |
