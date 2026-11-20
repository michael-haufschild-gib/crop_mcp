# Vision Tools MCP

Vision Tools is a local stdio MCP server for measuring screenshot geometry, sampling colors and checking text contrast. Setup and client registration are in the [README](README.md#set-up-once).

## Required reading

- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [Style guide](docs/meta/styleguide.md)

## Project constraints

- Reserve server stdout for MCP messages. Send diagnostics and setup instructions to stderr.
- Keep image operations usable as Python functions. Raise descriptive validation errors there and translate exceptions into MCP error results at the server boundary.
- Use Pillow for image operations and NumPy for numerical work. Keep the runtime free of SciPy, scikit-learn and PyTorch.
- Use normalized coordinates in the original, display-oriented image. Pixel boxes use exclusive right and bottom edges.
- Keep Python files at or below 750 lines and functions at or below McCabe complexity 10 and 40 statements. Run the quality gate before committing.

## Commands

Run from the repository root. The Make targets use the checkout's development environment on macOS and Linux. For Windows setup and test commands, see the [testing guide](docs/testing.md#running-tests).

| Command | Purpose |
|---|---|
| `make setup` | Install the locked development dependencies in the checkout environment. |
| `make serve` | Run the server on stdio. |
| `make lint` | Run Ruff and the test assertion linter. |
| `make format` / `make format-check` | Apply or check Ruff formatting. |
| `make typecheck` | Run strict mypy. |
| `make unit-test` / `make smoke-test` | Run unit or integration tests without coverage. |
| `make test` | Run the full automated suite with coverage. |
| `make check` | Run lint, format checks, type checks, tests and the file-length check sequentially. |
| `make live-qa` | Generate deterministic images for the [manual checklist](tests/live_qa_checklist.md). |
| `make clean` | Remove local development caches and build products. |

## Working with screenshots

Use the grid on the original image to locate the object. For a flat fill, use `measure_at` inside it. For a textured target, inspect the natural crop alongside the detailed view. Use an unannotated source region for palette measurements. [Measurement workflow](README.md#measuring-a-screenshot)

Record decisions that affect future changes in `docs/adr/`. Keep evidence for a measured change alongside its report in `docs/benchmarks/`. The shared instructions belong in this file and its Codex counterpart. When editing them, regenerate `AGENTS.md` with the same content and ordinary Markdown links for the three imports.
