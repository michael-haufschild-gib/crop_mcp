"""Detect placeholder tests and assertions that only check a result's shape."""

from __future__ import annotations

import argparse
import ast
import sys
import tokenize
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def _checks_nonempty(left: ast.expr, op: ast.cmpop, right: ast.expr) -> bool:
    if isinstance(op, ast.NotEq):
        match right:
            case ast.List(elts=[]) | ast.Dict(keys=[]) | ast.Tuple(elts=[]):
                return True
            case ast.Constant(value=""):
                return True
    if not isinstance(right, ast.Constant):
        return False
    match left:
        case ast.Call(func=ast.Name(id="len"), args=[_]):
            return (right.value == 0 and isinstance(op, (ast.Gt, ast.NotEq))) or (
                right.value == 1 and isinstance(op, ast.GtE)
            )
    return False


def _shallow_comparison(left: ast.expr, op: ast.cmpop, right: ast.expr) -> bool:
    if isinstance(op, (ast.IsNot, ast.NotEq)) and any(
        isinstance(side, ast.Constant) and side.value is None for side in (left, right)
    ):
        return True
    if isinstance(op, (ast.Eq, ast.Is)) and any(
        isinstance(side, ast.Call) and isinstance(side.func, ast.Name) and side.func.id == "type"
        for side in (left, right)
    ):
        return True
    return _checks_nonempty(left, op, right)


def _shallow(expr: ast.expr) -> bool:
    if not any(isinstance(node, (ast.Name, ast.Call, ast.Attribute)) for node in ast.walk(expr)):
        return True  # All operands are literals.
    match expr:
        case (
            ast.Name()
            | ast.Attribute()
            | ast.Subscript()
            | ast.UnaryOp(op=ast.Not(), operand=ast.Name() | ast.Attribute() | ast.Subscript())
        ):
            return True
        case ast.Call(func=ast.Name(id="bool" | "len" | "hasattr" | "isinstance" | "type")):
            return True
        case ast.Call(func=ast.Name(), args=[], keywords=[]):
            return True
        case ast.Compare(left=left, ops=[op], comparators=[right]):
            return _shallow_comparison(left, op, right)
    return False


def _placeholder(stmt: ast.stmt) -> bool:
    match stmt:
        case ast.Pass() | ast.Expr(value=ast.Constant()) | ast.Return(value=None | ast.Constant()):
            return True
    return False


def _assertions(node: ast.AST) -> Iterator[ast.Assert]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assert):
            yield child
        elif not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from _assertions(child)


def _diagnostics(path: Path) -> list[str]:
    with tokenize.open(path) as source:
        module = ast.parse(source.read(), filename=str(path))
    findings: list[tuple[int, str]] = []
    for test in ast.walk(module):
        if not isinstance(test, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not test.name.startswith("test_"):
            continue
        if all(_placeholder(stmt) for stmt in test.body):
            findings.append((test.lineno, f"empty test {test.name}"))
        findings.extend(
            (
                node.lineno,
                f"{ast.unparse(node.test)} — assert the expected value or observable effect.",
            )
            for node in _assertions(test)
            if _shallow(node.test)
        )
    return [f"{path}:{line}: {message}" for line, message in sorted(findings)]


def main() -> int:
    """Lint named pytest modules or discover test_*.py recursively in directories."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    paths: list[Path] = parser.parse_args().paths
    files: set[Path] = set()
    for path in paths:
        if path.is_dir():
            files.update(path.rglob("test_*.py"))
        else:
            files.add(path)
    if not files:
        parser.error("no test modules found")
    failed = False
    for file in sorted(files):
        try:
            messages = _diagnostics(file)
        except (OSError, SyntaxError) as exc:
            parser.exit(2, f"{exc}\n")
        if messages:
            sys.stderr.write("\n".join(messages) + "\n")
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
