# Testing Guide for LLM Coding Agents

**Purpose**: Instructions for testing tools and verifying changes.
**Read This When**: Modifying a tool, adding a new tool, or verifying the server works.
**Stack**: Python 3.9+, pytest, mypy --strict

## Test Commands

| Command | Purpose |
|-|-|
| `make test` | Run full test suite |
| `make check` | Full pipeline: lint + format + typecheck + test + file length |
| `make smoke-test` | Quick integration tests |
| `make live-qa` | Generate images for live MCP QA (see below) |
| `~/.vision-tools-env/bin/pytest tests/test_crop.py -v` | Run tests for a single module |
| `~/.vision-tools-env/bin/mypy .` | Type-check all files (strict mode) |

## Test Layers

The test suite has three layers, each catching different classes of bugs:

| Layer | Command | What it catches |
|-|-|-|
| Unit tests | `make test` | Logic errors in individual functions |
| Integration tests | `make smoke-test` | Breakage across module boundaries |
| Live MCP QA | `make live-qa` + checklist | MCP transport issues, tool usability from the AI consumer's perspective |

Unit and integration tests run in CI. Live QA is a manual procedure run after tool changes or before releases.

## Test Structure

```
tests/
  conftest.py              Shared fixtures (synthetic_image, solid_color_image)
  test_validators.py       validate_image_path, validate_coordinates
  test_crop.py             crop_image, image_info
  test_grid.py             Pixel-level grid rendering assertions
  test_colors.py           _kmeans, extract_colors
  test_cleanup.py          cleanup_temp_dir LRU eviction
  test_contrast.py         WCAG contrast ratio, HSL/OKLCH conversions
  test_validate_region.py  _validate_region optional coordinate validation
  test_server.py           MCP wiring, JSON serialization, error handling
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
| LRU eviction | Verify oldest files are removed when temp dir exceeds limit |

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

Automated tests use synthetic images from fixtures exclusively. `tests/live_qa_images/` contains generated images for manual QA (gitignored). Real screenshots may exist in `screenshots/` for manual verification only.

## Common Mistakes

- **Don't**: Assert only existence (`assert result is not None`). **Do**: Assert specific values against known inputs.
- **Don't**: Use real screenshots in automated tests (non-deterministic). **Do**: Create synthetic images with fixtures.
- **Don't**: Skip testing error paths. **Do**: Verify `ValueError` is raised for invalid inputs.
- **Don't**: Sample grid pixels at intersections of multiple gridlines. **Do**: Choose y/x positions between gridline intervals.
