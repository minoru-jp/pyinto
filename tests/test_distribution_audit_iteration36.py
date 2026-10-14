"""Distribution boundaries remain correct after moving C to developer-only fixtures."""

from __future__ import annotations

import inspect
import tomllib
from pathlib import Path
from typing import Any

from pyinto import convert, realize

ROOT = Path(__file__).resolve().parents[1]


def _project(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_only_host_has_distributable_project_metadata() -> None:
    host = _project(ROOT / "pyproject.toml")
    assert host["project"]["name"] == "pyinto"
    assert host["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert not (ROOT / "targets" / "c" / "pyproject.toml").exists()
    assert (ROOT / "tests" / "support" / "c_realizer" / "pack.py").is_file()
    assert (ROOT / "tests" / "support" / "python_realizer" / "pack.py").is_file()
    assert not (ROOT / "src" / "pyinto_target_c").exists()
    assert not (ROOT / "src" / "tests").exists()


def test_development_contracts_are_excluded_from_host_distribution() -> None:
    """Test contract fixtures stay in source, but needn't ship to customers."""
    host = _project(ROOT / "pyproject.toml")
    find = host["tool"]["setuptools"]["packages"]["find"]
    assert "pyinto.contracts" in find["exclude"]
    assert "pyinto.contracts.*" in find["exclude"]
    assert (ROOT / "src" / "pyinto" / "contracts" / "port_contract.py").is_file()
    assert not (ROOT / "src" / "pyinto" / "targets").exists()


def test_surface_requires_explicit_realization_selection() -> None:
    for func in (convert, realize):
        parameter = inspect.signature(func).parameters["realizations"]
        assert parameter.default is inspect.Parameter.empty
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
