"""Regression tests for English published document deployment."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_published_english_documents_in_sync() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/published_docs.py"), "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_published_document_coverage_is_explicit() -> None:
    data = json.loads(
        (ROOT / "devdocs/config/published_en.json").read_text(encoding="utf-8")
    )
    assert data["schema"] == 1
    assert set(data["entries"]) == {
        "README.md",
        "STATUS.md",
        "CHANGELOG.md",
        "GLOSSARY.md",
        "specification/INDEX.md",
        "specification/construct.md",
        "specification/frontend.md",
        "specification/composition.md",
        "specification/conversion.md",
        "target_implementation/INDEX.md",
        "target_implementation/implementation-guide.md",
        "target_implementation/declaration-reference.md",
        "target_implementation/construct-reference.md",
        "target_implementation/admission-reference.md",
        "target_implementation/verification-guide.md",
    }
    assert data["entries"]["README.md"]["coverage"] == "translated"
    assert data["entries"]["STATUS.md"]["coverage"] == "translated"
    assert data["entries"]["CHANGELOG.md"]["coverage"] == "translated"
    assert data["entries"]["specification/construct.md"]["coverage"] == "translated"
    assert data["entries"]["specification/composition.md"]["coverage"] == "translated"


def test_distribution_metadata_points_to_english_readme() -> None:
    import tomllib

    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert meta["project"]["readme"]["file"] == "README.md"


def test_full_composition_translation_preserves_clause_fields() -> None:
    import importlib.util

    script = ROOT / "scripts/published_docs.py"
    spec = importlib.util.spec_from_file_location("published_docs", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = (
        ROOT / "devdocs/canonical_documents/specification/composition.md"
    ).read_text(encoding="utf-8")
    english = (ROOT / "docs/specification/composition.md").read_text(encoding="utf-8")
    assert module.translated_composition_errors(original, english) == []
    assert "English contract synopsis (abridged)" not in english
    assert len(original.split("\n## CMP_")) == len(english.split("\n## CMP_"))


def test_unabridged_composition_checker_rejects_missing_fields() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_docs", ROOT / "scripts/published_docs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (
        ROOT / "devdocs/canonical_documents/specification/composition.md"
    ).read_text(encoding="utf-8")
    english = (ROOT / "docs/specification/composition.md").read_text(encoding="utf-8")
    assert module.translated_composition_errors(
        source, english.replace("level: INFORMATIVE", "level: MUST", 1)
    )
    assert module.translated_composition_errors(
        source, english.replace("related: [CST_075](construct.md#cst_075)", "", 1)
    )


def test_full_construct_translation_preserves_clause_fields() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_docs", ROOT / "scripts/published_docs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = (
        ROOT / "devdocs/canonical_documents/specification/construct.md"
    ).read_text(encoding="utf-8")
    english = (ROOT / "docs/specification/construct.md").read_text(encoding="utf-8")
    assert (
        module.translated_contract_errors(
            original, english, prefix="CST", label="Construct Model"
        )
        == []
    )
    assert "English contract synopsis (abridged)" not in english
    assert len(original.split("\n## CST_")) == len(english.split("\n## CST_"))


def test_full_construct_checker_rejects_contract_field_regressions() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_docs", ROOT / "scripts/published_docs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (
        ROOT / "devdocs/canonical_documents/specification/construct.md"
    ).read_text(encoding="utf-8")
    english = (ROOT / "docs/specification/construct.md").read_text(encoding="utf-8")
    assert module.translated_contract_errors(
        source,
        english.replace("level: MUST", "level: INFORMATIVE", 1),
        prefix="CST",
        label="Construct Model",
    )
    assert module.translated_contract_errors(
        source,
        english.replace("title: Normalized structure and named child parts", "", 1),
        prefix="CST",
        label="Construct Model",
    )


def test_full_frontend_translation_preserves_clause_fields() -> None:
    """The complete English Frontend specification retains Japanese clause fields."""
    import importlib.util

    script = ROOT / "scripts/published_docs.py"
    spec = importlib.util.spec_from_file_location("published_docs_frontend", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = (
        ROOT / "devdocs/canonical_documents/specification/frontend.md"
    ).read_text(encoding="utf-8")
    published = (ROOT / "docs/specification/frontend.md").read_text(encoding="utf-8")
    assert (
        module.translated_contract_errors(
            original, published, prefix="FRT", label="Python Frontend"
        )
        == []
    )
    assert "English contract synopsis (abridged)" not in published
    # Ensure the most substantial contract and latest clauses retain detailed content.
    assert "InterfaceVariadicParameter" in published
    assert "ClassDecorationPlan" in published
    assert "target_once" in published
    assert "tuple[U, ...]" in published


def test_frontend_translation_checker_detects_loss_of_normative_field() -> None:
    import importlib.util

    script = ROOT / "scripts/published_docs.py"
    spec = importlib.util.spec_from_file_location(
        "published_docs_frontend_mutation", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = (
        ROOT / "devdocs/canonical_documents/specification/frontend.md"
    ).read_text(encoding="utf-8")
    published = (ROOT / "docs/specification/frontend.md").read_text(encoding="utf-8")
    assert any(
        "normative level changed" in error
        for error in module.translated_contract_errors(
            original,
            published.replace("level: MUST", "level: SHOULD", 1),
            prefix="FRT",
            label="Python Frontend",
        )
    )


def test_published_link_checker_ignores_inline_code(tmp_path: Path) -> None:
    import importlib.util

    script = ROOT / "scripts/published_docs.py"
    spec = importlib.util.spec_from_file_location("published_docs_link_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    document = tmp_path / "example.md"
    document.write_text("An indexed function call `t[0](args)` is not a link.\n")
    # Only test the local link-scanning logic, without relying on actual link paths.
    # internal_link_errors computes relative paths against ROOT when reporting failures.
    assert module.internal_link_errors(document) == []


def test_full_status_translation_matches_section_and_item_structure() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_status_check", ROOT / "scripts/published_docs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    japanese = (ROOT / "devdocs/canonical_documents/STATUS.md").read_text()
    english = (ROOT / "STATUS.md").read_text()
    assert module.translated_status_errors(japanese, english) == []
    assert len(english) > 40_000


def test_status_checker_detects_omitted_implemented_item() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_status_mutation", ROOT / "scripts/published_docs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    japanese = (ROOT / "devdocs/canonical_documents/STATUS.md").read_text()
    english = (ROOT / "STATUS.md").read_text()
    modified = english.replace(
        "- **Iteration 46, typed variadic arguments for self-defined functions:**",
        "Iteration 46, typed variadic arguments for self-defined functions:",
        1,
    )
    assert "bullet count differs" in str(
        module.translated_status_errors(japanese, modified)
    )


def test_changelog_translation_preserves_historical_entries() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_changelog_check", ROOT / "scripts/published_docs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = (ROOT / "devdocs/canonical_documents/CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    english = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert module.translated_changelog_errors(original, english) == []
    assert "not yet a complete translation" not in english


def test_changelog_checker_rejects_missing_entry_and_contract() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "published_changelog_mutation", ROOT / "scripts/published_docs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = (ROOT / "devdocs/canonical_documents/CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    english = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entries = [line for line in english.splitlines() if line.startswith("- ")]
    assert entries
    without_entry = english.replace(entries[0] + "\n", "", 1)
    assert any(
        "entry count differs" in issue
        for issue in module.translated_changelog_errors(original, without_entry)
    )
    without_contract = english.replace("CST_073", "CST_999", 1)
    assert any(
        "contract IDs differ" in issue
        for issue in module.translated_changelog_errors(original, without_contract)
    )


def test_complete_english_publication_release_check() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/published_docs.py"), "release-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
