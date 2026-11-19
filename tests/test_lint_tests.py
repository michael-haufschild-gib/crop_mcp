"""Exercise the test linter on independent source files without importing them."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_LINTER = Path(__file__).resolve().parents[1] / "scripts" / "lint_tests.py"


def _lint(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_LINTER), str(path)], capture_output=True, text=True, check=False
    )


def test_reports_each_shallow_assertion_and_placeholder_with_its_location(tmp_path: Path) -> None:
    tests = tmp_path / "nested"
    tests.mkdir()
    module = tests / "test_shapes.py"
    expressions = [
        "True",
        "2 + 2 == 4",
        "result",
        "read_result()",
        "not result.colors",
        "result['palette']",
        "result is not None",
        "None != result",
        "bool(result)",
        "isinstance(result, dict)",
        "hasattr(result, 'size')",
        "type(result) is dict",
        "result != []",
        "len(result) > 0",
        "len(result) >= 1",
    ]
    statements = "".join(f"        assert {expr}\n" for expr in expressions)
    module.write_text(
        "class TestPalette:\n    async def test_shape(self):\n"
        + statements
        + "def test_unimplemented():\n    ...\n",
        encoding="utf-8",
    )
    result = _lint(tmp_path)
    assert result.returncode == 1
    assert [line.split(": ", 1)[0] for line in result.stderr.splitlines()] == [
        f"{module}:{n}" for n in range(3, 4 + len(expressions))
    ]
    assert "empty test test_unimplemented" in result.stderr


def test_accepts_exact_results_empty_results_and_observable_effects(tmp_path: Path) -> None:
    module = tmp_path / "test_values.py"
    module.write_text(
        "raise RuntimeError('lint must never execute this module')\n"
        "def test_values():\n"
        "    def read_value(value):\n"
        "        assert value is not None\n"
        "        return value['width']\n"
        "    assert read_value(crop()) == 15\n"
        "    assert optional() is None\n"
        "    assert missing() == []\n"
        "    assert len(palette()) == 3\n"
        "    assert saved.read_bytes() == expected\n",
        encoding="utf-8",
    )
    result = _lint(module)
    assert (result.returncode, result.stderr) == (0, "")


def test_unreadable_input_cannot_pass(tmp_path: Path) -> None:
    result = _lint(tmp_path / "missing.py")
    assert result.returncode == 2
    assert "missing.py" in result.stderr
