"""Stage 6: Python realization is a developer-only test tool."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pyinto import convert
from pyinto.constructs import ConstructError
from tests.support.python_realizer.pack import python_bindings

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "src" / "pyinto"
TEST_REALIZER = ROOT / "tests" / "support" / "python_realizer" / "pack.py"


def test_python_realizer_is_not_in_host_package() -> None:
    assert TEST_REALIZER.is_file()
    assert not (HOST / "targets").exists()
    for module in HOST.rglob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]
        imports.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            name.startswith("tests.support.python_realizer") for name in imports
        ), module


def test_python_realizer_preserves_existing_dev_behavior() -> None:
    output = convert("n: int = 2\nprint('ok')", realizations=python_bindings())
    assert output == "n = 2\nprint('ok')\n"
    # The old helper intentionally loses annotations. Stage 6 is a move, not a feature extension.
    assert output != "n: int = 2\nprint('ok')\n"


def test_python_realizer_still_rejects_unimplemented_constructs() -> None:
    with pytest.raises(ConstructError):
        convert("n: int = 1\nn = n + 1", realizations=python_bindings())
