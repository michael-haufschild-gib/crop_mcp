# Vision Tools MCP

MCP server providing `crop_to_magnify_image`, `get_image_coordinates_grid`, `extract_colors`, and `check_contrast` tools for Claude Code.

## Constraints

| Constraint | Rule |
|-|-|
| No stdout | Never print to stdout — breaks stdio transport. Use `logging` to stderr. |
| No heavy deps | numpy only for math. No scipy, sklearn, or torch. |
| Never crash | Tool functions catch all exceptions and return error JSON. |
| 0-1 coordinates | All coordinates normalized. `(0,0)` = top-left, `(1,1)` = bottom-right. |
| Lint clean | All code must pass `make check` before commit. Zero warnings. |
| Max 750 lines | No Python file may exceed 750 lines. Split into modules. |
| Max complexity 10 | No function may exceed McCabe complexity 10 or 40 statements. |

## Required Reading

@docs/architecture.md
@docs/testing.md
@docs/meta/styleguide.md

## Commands

| Command | Purpose |
|-|-|
| `make setup` | Create venv + install deps (safe to re-run) |
| `make check` | Full pipeline: lint + format + typecheck + test + file length |
| `make test` | Run pytest suite |
| `make lint` | Run ruff check |
| `make format` | Auto-format all files |
| `make typecheck` | Run mypy (strict mode) |
| `make smoke-test` | Quick integration tests |
| `make live-qa` | Generate images for live MCP QA (`tests/live_qa_checklist.md`) |
| `make serve` | Start MCP server (stdio) |
| `make clean` | Remove caches and build artifacts |
