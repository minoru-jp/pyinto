"""Executable documentation contract checks for the Target authoring guides."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from devdocs.canonical_sources.target_implementation.admission_reference import (
    baseline_rule_rows,
)
from devdocs.canonical_sources.target_implementation.construct_reference import (
    language_variant_rows,
)
from devdocs.canonical_sources.target_implementation.examples import (
    COMPOSITION_EXAMPLE,
    STRUCTURAL_EXAMPLE,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET_DOCS = ROOT / "devdocs" / "canonical_documents" / "target_implementation"


def _run_snippet(source: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    subprocess.run([sys.executable, "-c", source], cwd=ROOT, env=env, check=True)


def test_structural_projection_example_executes() -> None:
    """Example is a real external Target created only with public Host APIs."""
    _run_snippet(STRUCTURAL_EXAMPLE)


def test_composition_text_example_executes() -> None:
    _run_snippet(COMPOSITION_EXAMPLE)


def test_rendered_guide_keeps_the_exact_executable_examples() -> None:
    text = (TARGET_DOCS / "implementation-guide.md").read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)\n```", text, flags=re.DOTALL)
    assert len(snippets) == 2
    assert snippets == [
        STRUCTURAL_EXAMPLE.rstrip("\n"),
        COMPOSITION_EXAMPLE.rstrip("\n"),
    ]


def test_construct_variant_table_matches_model() -> None:
    text = (TARGET_DOCS / "construct-reference.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([^|]+) \| ([^|]+) \| ([^|]*) \|$", text, re.MULTILINE)
    assert rows[0] == ("Construct", "variant_domain()", "備考")
    assert rows[2:] == list(language_variant_rows())


def test_index_points_to_all_generated_guide_pages() -> None:
    index = (TARGET_DOCS / "INDEX.md").read_text(encoding="utf-8")
    for name in (
        "implementation-guide.md",
        "declaration-reference.md",
        "construct-reference.md",
        "admission-reference.md",
        "verification-guide.md",
    ):
        assert (TARGET_DOCS / name).exists()
        assert f"]({name})" in index


def test_admission_table_matches_baseline_rules() -> None:
    text = (TARGET_DOCS / "admission-reference.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([^|]+) \| ([^|]+) \| ([^|]*) \|$", text, re.MULTILINE)
    assert ("Rule", "対象Construct", "宣言可能な契約キー/ファミリー") in rows
    first = rows.index(("Rule", "対象Construct", "宣言可能な契約キー/ファミリー"))
    assert rows[first + 2 : first + 2 + len(baseline_rule_rows())] == list(
        baseline_rule_rows()
    )
