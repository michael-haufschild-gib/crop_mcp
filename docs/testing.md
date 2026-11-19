# Testing Guide for LLM Coding Agents

**Purpose**: Instructions for testing tools and verifying changes.
**Read This When**: Modifying a tool, adding a new tool, or verifying the server works.
**Stack**: Python 3.12+, pytest, mypy --strict

## Test Commands

| Command | Purpose |
|-|-|
| `make lint` | Check Python code, image-tool import boundaries and test assertions |
| `make unit-test` | Run tests outside the integration layer |
| `make test` | Run all automated tests and enforce the existing 90% line coverage floor |
| `make check` | Full pipeline: lint + format + typecheck + test + file length |
| `make smoke-test` | Run the image pipeline and MCP host tests marked `integration` |
| `make live-qa` | Generate images for live MCP QA (see below) |
| `.vision-tools-env/bin/pytest tests/test_crop.py -v` | Run tests for a single module |
| `.vision-tools-env/bin/mypy .` | Type-check all files (strict mode) |

## Test Layers

The test suite has three layers, each catching different classes of bugs:

| Layer | Command | What it catches |
|-|-|-|
| Unit tests | `make unit-test` | Logic errors in individual functions and regressions in development tooling |
| Integration tests | `make smoke-test` | Geometry or palette drift across tools, incompatible public schemas, broken stdio replies and shutdown failures |
| Live MCP QA | `make live-qa` + checklist | MCP transport issues, tool usability from the AI consumer's perspective |

Unit and integration tests run in CI. Live QA is a manual procedure run after tool changes or before releases.

Pytest strict mode rejects unknown configuration and markers, duplicate parameter IDs, and unexpected passes of expected-failure tests. Mark real host and cross-tool tests with `@pytest.mark.integration`. The shared fixtures give each test its own temporary runtime root. The stdio client also starts its subprocess with a private working directory and temporary directory. [Pytest strict mode](https://docs.pytest.org/en/stable/reference/reference.html#confval-strict)

### Linting a change

Ruff enforces the size and complexity rules on functions, checks exception assertions and rejects blanket suppressions, unused parameters, debugger statements and runtime `assert` statements. Image operations under `tools/` cannot import the MCP protocol package, the server entry point, setup code or tests. [Ruff rules](https://docs.astral.sh/ruff/rules/)

The test linter parses `test_*.py` and reports file and line numbers for placeholder tests, literal-only assertions, and standalone checks of truthiness, type, presence or nonempty length. For example, a palette test should check the expected RGB triplet and percentage. Exact empty or missing results are valid expectations. Run `python scripts/lint_tests.py tests/test_colors.py` to check one module.

## Test Structure

```
tests/
  conftest.py              Shared fixtures (synthetic_image, solid_color_image)
  test_validators.py       validate_image_path, validate_coordinates
  test_crop.py             crop_image, image_info
  test_grid.py             Pixel-level grid rendering assertions
  test_colors.py           _kmeans, extract_colors
  test_cleanup.py          Parallel hosts, retention limits, cancellation, shutdown and crash recovery
  test_contrast.py         WCAG contrast ratio, HSL/OKLCH conversions
  test_validate_region.py  _validate_region optional coordinate validation
  test_server.py           MCP wiring, JSON serialization, error handling
  stdio_client.py          Start a real server, correlate JSON-RPC replies and verify shutdown
  test_lint_tests.py       Check which test sources the assertion linter accepts and rejects
  test_integration.py      End-to-end pipeline: info → crop → colors
  generate_live_images.py  Generates deterministic images for live QA
  live_qa_checklist.md     Step-by-step MCP QA procedure (13 test cases)
  live_qa_images/          Generated images (gitignored)
```

## Shared Fixtures (conftest.py)

| Fixture | Description |
|-|-|
| `synthetic_image` | 200x100 PNG: left half red, right half blue |
| `solid_color_image(color, size)` | Factory: creates a solid-color PNG |
| `tmp_path` | Built-in pytest fixture: temp directory per test |

## How to Add Tests for a New Tool

1. Create `tests/test_{tool_name}.py`.
2. Import the tool function from `tools/{tool_name}.py`.
3. Use `synthetic_image` or `solid_color_image` fixtures for deterministic inputs.
4. Test happy paths with specific value assertions (not just existence checks).
5. Test error paths: invalid input raises `ValueError` with helpful message.
6. Run `make check` to verify all checks pass.

**Template:**

```python
"""Tests for new_tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.new_tool import tool_name


class TestToolName:
    def test_happy_path(self, synthetic_image: Path) -> None:
        result = tool_name(str(synthetic_image), ...)
        assert result["key"] == expected_value

    def test_invalid_input_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="expected message"):
            tool_name(str(tmp_path / "nonexistent.png"))
```

## What to Test

| Tool aspect | How to verify |
|-|-|
| Correct output values | Assert against known inputs (solid colors, known dimensions) |
| Coordinate accuracy | Crop a known region, verify output dimensions and pixel colors |
| Error handling | Call with invalid path, out-of-range coords — verify ValueError |
| Edge cases | Zero padding, full-image region, RGBA/palette inputs |
| Grid rendering | Pixel-level color assertions at known gridline positions |
| Color extraction | Verify hex values match known solid-color inputs |
| JSON serialization | Verify tool output serializes and deserializes correctly |
| Image lifetime | Verify whole-result eviction, two live hosts sharing a cache with distinct temporary directories, cleanup on EOF and SIGTERM, and recovery after a hard kill during export |

## Live MCP QA

Tests the full MCP tool chain from the AI consumer's perspective — something unit tests cannot cover. Catches: MCP transport errors, JSON serialization issues, tool description ambiguity, grid overlay readability, and multi-tool pipeline failures.

**When to run**: After modifying tool behavior, changing tool descriptions, or before a release.

**Procedure**:

1. Run `make live-qa` to generate test images with known ground truth.
2. Open `tests/live_qa_checklist.md` and execute each test case using the MCP tools.
3. Compare results against the expected values in the checklist.

The checklist covers all 4 tools across 13 test cases, including a full pipeline chain (grid → crop → colors) and error handling.

**Test images** (`tests/generate_live_images.py`):

| Image | Size | Ground truth |
|-|-|-|
| `quadrants_400x400.png` | 400x400 | TL=#FF0000, TR=#00FF00, BL=#0000FF, BR=#FFFF00 |
| `color_bars_600x100.png` | 600x100 | 6 stripes: #FF0000, #FF8000, #FFFF00, #008000, #0000FF, #8000FF |
| `large_markers_2000x1000.png` | 2000x1000 | White + red markers at (0.25,0.25), (0.5,0.5), (0.75,0.75) |

## Test Images

### Blind screenshot geometry

Each case consists of a generated website, app or game background and one independently generated transparent foreground. The renderer trims the foreground, scales it, clears resampling fringes below alpha 16/255, and trims it again. It pastes the element once. The bounding box of the RGB difference between the entire composite and its pristine background must equal the placement box before a trial can start. The answer key records source dimensions, the half-open pixel box, normalized position and size, and the composite hash.

Generate the composites and key with `python -m tests.composite_geometry tests/live_qa_images/single-target`. Use `--density 2` to double the background resolution and rasterize the foreground at twice its native placement width. Use `--fit-5k` to preserve the aspect ratio inside a 5120 × 2880 viewport. The same PNG is attached in every condition at a given size.

Run `python -m tests.cold_geometry --scene ruins --density 1` for one unaided/aided pair. Omit `--scene` for all nine. The evaluator needs an authenticated Codex CLI with image input. For each trial it starts a fresh ephemeral session in a directory containing only the finished screenshot. The prompt names one target and asks for its four normalized edges. It records each MCP call, rejects unauthorized tool use, and keeps the background, foreground, and answer key out of the model context.

The scorer rounds predicted fractions to the nearest source pixel and reports signed errors for left, top, width and height. The original pass criterion requires all four edges to fall within two source pixels. The report also counts cases where position, width and height each fall within two source pixels. An exact box has zero error on every edge. The first three scenes are for development and the other six are held out. [Single-target results](benchmarks/single-target.md)

The native-resolution follow-up repeats every scene and reports the key and drone heights separately. It compares screenshot-only sessions, the previous MCP, and two crop changes. [Native height results and original pixels](benchmarks/native-height.md)

## Common Mistakes

- **Don't**: Assert only existence (`assert result is not None`). **Do**: Assert specific values against known inputs.
- **Don't**: Use real screenshots in automated tests (non-deterministic). **Do**: Create synthetic images with fixtures.
- **Don't**: Skip testing error paths. **Do**: Verify `ValueError` is raised for invalid inputs.
- **Don't**: Sample grid pixels at intersections of multiple gridlines. **Do**: Choose y/x positions between gridline intervals.
