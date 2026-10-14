"""The distributable Host and the non-distributable C fixture have a one-way API boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from pyinto import convert
from pyinto.realizations import RealizationRegistry
from tests.support.c_realizer import c_bindings

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "src" / "pyinto"
C_TARGET = ROOT / "tests" / "support" / "c_realizer"
PYTHON_TARGET = ROOT / "tests" / "support" / "python_realizer"


def _imports(file: Path) -> set[str]:
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            result.add(node.module)
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
    return result


def test_reference_targets_live_outside_the_host_distribution() -> None:
    assert C_TARGET.joinpath("pack.py").is_file()
    assert PYTHON_TARGET.joinpath("pack.py").is_file()
    assert not (ROOT / "targets" / "c").exists()
    assert not HOST.joinpath("realizations", "c.py").exists()
    assert not HOST.joinpath("targets").exists()


def test_host_cannot_import_development_target_implementations() -> None:
    """Host modules never import a fixture or an older C shortcut."""
    prohibited = (
        "pyinto_target_c",
        "tests",
        "pyinto.targets.c",
        "pyinto.realizations.c",
    )
    for module in HOST.rglob("*.py"):
        for name in _imports(module):
            assert not any(
                name == prefix or name.startswith(prefix + ".") for prefix in prohibited
            ), (module, name)


def test_reference_targets_use_public_pyinto_modules_only() -> None:
    """Both reference implementations exercise the Host's public APIs."""
    permitted = {
        "pyinto.constructs",
        "pyinto.interfaces",
        "pyinto.model",
        "pyinto.realizations.layout",
        "pyinto.realizations.registry",
        "pyinto.realizations.regulation",
    }
    for fixture in (C_TARGET, PYTHON_TARGET):
        for module in fixture.rglob("*.py"):
            for name in _imports(module):
                if name == "pyinto" or name.startswith("pyinto."):
                    assert name in permitted, (module, name)


def test_c_implementation_is_selected_explicitly() -> None:
    registry = c_bindings()
    assert isinstance(registry, RealizationRegistry)
    assert registry.target == "c"
    assert 'puts("hello")' in convert('print("hello")', realizations=registry)
