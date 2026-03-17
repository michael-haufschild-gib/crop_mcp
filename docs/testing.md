# Testing Guide for LLM Coding Agents

**Purpose**: Instructions for testing tools and verifying changes.
**Read This When**: Modifying a tool, adding a new tool, or verifying the server works.
**Stack**: Python 3.9+, pytest, mypy --strict

## Test Commands

| Command | Purpose |
|-|-|
| `make test` | Run full test suite |
| `make check` | Run full pipeline: lint + format + typecheck + test + file length |
| `~/.vision-tools-env/bin/pytest tests/test_crop.py -v` | Run tests for a single module |
| `~/.vision-tools-env/bin/mypy .` | Type-check all files (strict mode) |
| `~/.vision-tools-env/bin/python3 server.py --test` | Quick smoke test (no pytest needed) |

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

## Self-Test (Smoke Test)

The self-test in `server.py --test` is a quick sanity check that does not require pytest. It creates a synthetic image and verifies basic functionality. The pytest suite is the authoritative test source.

## Test Images

`tests/` may contain real screenshots for manual verification only. Automated tests use synthetic images exclusively.

## Common Mistakes

- **Don't**: Assert only existence (`assert result is not None`). **Do**: Assert specific values against known inputs.
- **Don't**: Use real screenshots in automated tests (non-deterministic). **Do**: Create synthetic images with fixtures.
- **Don't**: Skip testing error paths. **Do**: Verify `ValueError` is raised for invalid inputs.
- **Don't**: Sample grid pixels at intersections of multiple gridlines. **Do**: Choose y/x positions between gridline intervals.
