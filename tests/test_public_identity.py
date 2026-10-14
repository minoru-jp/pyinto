"""Public distribution identity and canonical vocabulary regression checks."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pyinto

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_and_import_name_are_pyinto() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["name"] == "pyinto"
    assert pyinto.__name__ == "pyinto"
    assert (ROOT / "src" / "pyinto" / "__init__.py").is_file()


def test_canonical_glossary_covers_shared_concepts() -> None:
    glossary = (ROOT / "devdocs" / "canonical_documents" / "GLOSSARY.md").read_text(
        encoding="utf-8"
    )
    for term in (
        "Model",
        "Construct",
        "Interface",
        "Realization",
        "Template",
        "Slot",
        "Frontend",
        "Composer",
        "Renderer",
        "pyinto",
    ):
        assert f"## {term}\n" in glossary


def test_current_architecture_glossary_and_readme() -> None:
    """Glossary and README present the current architecture and guide links."""
    documents = ROOT / "devdocs" / "canonical_documents"
    glossary = (documents / "GLOSSARY.md").read_text(encoding="utf-8")
    for term in (
        "Host",
        "Surface",
        "Foundation",
        "Language Construct",
        "Python Source Adapter",
        "Interface Mapping",
        "Target Implementation",
        "Language Implementation",
        "Interface Implementation",
        "Bundle",
    ):
        assert f"## {term}\n" in glossary
    assert "## Target Cartridge\n" not in glossary
    assert "## taiou\n" not in glossary

    readme = (documents / "README.md").read_text(encoding="utf-8")
    for concept in (
        "# pyinto\n",
        "pyinto Host",
        "Construct Model",
        "Target Implementation",
        "pip install pyinto",
        "__pyinto_runtime__",
    ):
        assert concept in readme
    for guide in (
        "](STATUS.md)",
        "](target_implementation/INDEX.md)",
        "](specification/INDEX.md)",
    ):
        assert guide in readme


def test_realization_api_identity() -> None:
    """Registration and API expose Realization rather than old Binding names."""
    import inspect

    from pyinto import convert, realize
    from pyinto.realizations import RealizationRegistry
    from pyinto.realizations.layout import Template, Text
    from pyinto.realizations.registry import EmitContext

    assert RealizationRegistry.__name__ == "RealizationRegistry"
    assert "realizations" in inspect.signature(convert).parameters
    assert "realizations" in inspect.signature(realize).parameters
    assert "bindings" not in inspect.signature(realize).parameters
    assert Template is not Text
    assert "registry" in EmitContext.__dataclass_fields__
