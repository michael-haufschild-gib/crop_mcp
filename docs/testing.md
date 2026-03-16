# Testing Guide for LLM Coding Agents

**Purpose**: Instructions for testing tools and verifying changes.
**Read This When**: Modifying a tool, adding a new tool, or verifying the server works.
**Stack**: Python 3.9+, built-in self-test (no pytest)

## Test Commands

| Command | Purpose |
|-|-|
| `~/.vision-tools-env/bin/python3 server.py --test` | Run self-test of all tools |
| `~/.vision-tools-env/bin/python3 server.py` | Start server (verify no crash) |

## Self-Test Framework

Tests live in `_run_self_test()` in `server.py`. Each tool gets a section that:

1. Creates a synthetic test image with known properties.
2. Calls the tool function directly (not via MCP).
3. Asserts specific, verifiable outcomes.

**Template for new tool tests** (add inside `_run_self_test()`):

```python
# Test new_tool
from tools.new_tool import tool_name
result = tool_name(test_path, ...)
print(f"  tool_name: {result['key']}")
assert result["key"] == expected, f"Expected {expected}, got {result['key']}"
```

## What to Test

| Tool aspect | How to verify |
|-|-|
| Correct output values | Assert against known inputs (solid colors, known dimensions) |
| Coordinate accuracy | Crop a known region, verify output dimensions match |
| Error handling | Call with invalid path, out-of-range coords — verify ValueError |
| Edge cases | Zero padding, full-image region, single-pixel crop |

## Test Images

`tests/` contains real screenshots for manual verification. These are not used by the automated self-test (which creates synthetic images).

| File | Purpose |
|-|-|
| `tests/daily-rewards.png` | Real UI screenshot for manual crop testing |
| `tests/crops/` | Previously generated crop outputs |
| `tests/grid_experiments/` | Grid overlay iterations |

## Common Mistakes

- **Don't**: Assert only existence (`assert result is not None`). **Do**: Assert specific values against known inputs.
- **Don't**: Use real screenshots in the self-test (non-deterministic). **Do**: Create synthetic images with `Image.new()`.
- **Don't**: Skip testing error paths. **Do**: Verify `ValueError` is raised for invalid inputs.
