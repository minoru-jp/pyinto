"""Render and verify pyinto's Japanese canonical Markdown documents.

Usage:
    python scripts/docs.py render
    python scripts/docs.py check
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "devdocs" / "canonical_documents"
NOTICE = ROOT / "devdocs" / "config" / "notice.toml"
SOURCES = (
    "devdocs.canonical_sources.readme.canonical",
    "devdocs.canonical_sources.status.canonical",
    "devdocs.canonical_sources.changelog.canonical",
    "devdocs.canonical_sources.reviews.realization_boundary",
    "devdocs.canonical_sources.planning.pyinto_migration",
)
SPEC_MODULES = (
    "devdocs.canonical_sources.specification.construct",
    "devdocs.canonical_sources.specification.frontend",
    "devdocs.canonical_sources.specification.composition",
    "devdocs.canonical_sources.specification.conversion",
)
SPEC_PACKAGE = "devdocs.canonical_sources.specification"
TARGET_MODULES = (
    "devdocs.canonical_sources.realizer.implementation_guide",
    "devdocs.canonical_sources.realizer.declaration_reference",
    "devdocs.canonical_sources.realizer.construct_reference",
    "devdocs.canonical_sources.realizer.admission_reference",
    "devdocs.canonical_sources.realizer.verification_guide",
)
TARGET_PACKAGE = "devdocs.canonical_sources.realizer"
EXPECTED = (
    "README.md",
    "STATUS.md",
    "CHANGELOG.md",
    "GLOSSARY.md",
    "REALIZATION_BOUNDARY_AUDIT.md",
    "PYINTO_MIGRATION_PLAN.md",
    "specification/construct.md",
    "specification/frontend.md",
    "specification/composition.md",
    "specification/conversion.md",
    "specification/INDEX.md",
    "realizer/implementation-guide.md",
    "realizer/declaration-reference.md",
    "realizer/construct-reference.md",
    "realizer/admission-reference.md",
    "realizer/verification-guide.md",
    "realizer/INDEX.md",
)


def render(destination: Path) -> None:
    """Regenerate canonical documents and the Vocabulary glossary."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    development_stage = next(
        classifier.split(" - ", 1)[-1]
        for classifier in project["classifiers"]
        if classifier.startswith("Development Status :: ")
    )
    context = json.dumps(
        {
            "project": {
                "name": project["name"],
                "version": project["version"],
                "requires-python": project["requires-python"],
                "development_stage": development_stage,
            }
        },
        ensure_ascii=False,
    )
    # Ensure canonical source imports the checked-out Model, not another
    # installed pyinto version when docs are rendered by a developer.
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT / "src"), str(ROOT), env.get("PYTHONPATH", ""))
    )
    for module in SOURCES:
        command = [
            sys.executable,
            "-m",
            "shikumi_devdoc.cli",
            "render",
            "document",
            module,
            "-o",
            str(destination),
            "--notice",
            str(NOTICE),
        ]
        if not module.endswith("changelog.canonical"):
            command.extend(("--context", context))
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "shikumi_devdoc.cli",
            "render",
            "glossary",
            "devdocs.canonical_sources.vocabulary.canonical",
            "-o",
            str(destination / "GLOSSARY.md"),
            "--notice",
            str(NOTICE),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    specification_output = destination / "specification"
    specification_output.mkdir(parents=True, exist_ok=True)
    for module in SPEC_MODULES:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "shikumi_devdoc.cli",
                "render",
                "document",
                module,
                "-o",
                str(specification_output),
                "--notice",
                str(NOTICE),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "shikumi_devdoc.cli",
            "render",
            "index",
            SPEC_PACKAGE,
            "-o",
            str(specification_output),
            "--notice",
            str(NOTICE),
            "--index-title",
            "pyinto 現行仕様",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    target_output = destination / "realizer"
    target_output.mkdir(parents=True, exist_ok=True)
    for module in TARGET_MODULES:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "shikumi_devdoc.cli",
                "render",
                "document",
                module,
                "-o",
                str(target_output),
                "--notice",
                str(NOTICE),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "shikumi_devdoc.cli",
            "render",
            "index",
            TARGET_PACKAGE,
            "-o",
            str(target_output),
            "--notice",
            str(NOTICE),
            "--index-title",
            "Realizer 文書ガイド",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


def check() -> int:
    """Return nonzero when tracked canonical documents are out of date."""
    with tempfile.TemporaryDirectory(prefix="pyinto-docs-") as temporary:
        generated = Path(temporary)
        render(generated)
        differences = [
            name
            for name in EXPECTED
            if not (OUTPUT / name).is_file()
            or (OUTPUT / name).read_bytes() != (generated / name).read_bytes()
        ]
    if differences:
        print("Canonical documents are out of sync: " + ", ".join(differences))
        print("Run: python scripts/docs.py render")
        return 1
    print("Canonical documents are in sync.")
    return 0


def main() -> int:
    """Run the requested documentation workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("render", "check"))
    args = parser.parse_args()
    if args.action == "check":
        return check()
    render(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
