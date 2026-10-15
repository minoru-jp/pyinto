"""Release guard tests, independent of GitHub/PyPI access."""

from __future__ import annotations

import importlib.util
import io
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]["version"]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_tag_must_match_project_version() -> None:
    release = _load_script("verify_release")
    release.verify(f"v{VERSION}")
    with pytest.raises(ValueError, match="does not match"):
        release.verify("v9999.0.0")
    with pytest.raises(ValueError, match="does not match"):
        release.verify(VERSION)


def _create_packages(path: Path, *, include_target: bool = False) -> None:
    wheel = path / f"pyinto-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pyinto/__init__.py", "")
        archive.writestr(
            f"pyinto-{VERSION}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: pyinto\nVersion: {VERSION}\n"
            "Description-Content-Type: text/markdown\n\npyinto Host library\n",
        )
        if include_target:
            archive.writestr("pyinto/targets/c/__init__.py", "")
    with tarfile.open(path / f"pyinto-{VERSION}.tar.gz", "w:gz") as archive:
        for name in (
            "README.md",
            "LICENSE",
            "pyproject.toml",
            "docs/GLOSSARY.md",
            "docs/specification/INDEX.md",
            "docs/realizer/INDEX.md",
            "src/pyinto/__init__.py",
        ):
            data = b"test\n"
            member = tarfile.TarInfo(f"pyinto-{VERSION}/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


def test_distribution_guard_accepts_host_only_artifacts(tmp_path: Path) -> None:
    dist = _load_script("verify_dist")
    _create_packages(tmp_path)
    dist.verify(tmp_path)


def test_distribution_guard_rejects_bundled_target(tmp_path: Path) -> None:
    dist = _load_script("verify_dist")
    _create_packages(tmp_path, include_target=True)
    with pytest.raises(ValueError, match="excluded Target"):
        dist.verify(tmp_path)


def test_distribution_guard_rejects_missing_artifact(tmp_path: Path) -> None:
    dist = _load_script("verify_dist")
    with pytest.raises(ValueError, match="exactly one wheel"):
        dist.verify(tmp_path)


def test_push_and_release_use_same_reusable_quality_gate() -> None:
    workflows = ROOT / ".github" / "workflows"
    checks = (workflows / "checks.yml").read_text(encoding="utf-8")
    ci = (workflows / "ci.yml").read_text(encoding="utf-8")
    release = (workflows / "release.yml").read_text(encoding="utf-8")
    assert "workflow_call:" in checks
    assert "uses: ./.github/workflows/checks.yml" in ci
    assert "uses: ./.github/workflows/checks.yml" in release
    assert "python scripts/docs.py check" in checks
    assert "python scripts/published_docs.py release-check" in checks
    assert "python -m pytest -q" in checks
    assert "python -m build" in checks
    assert "python scripts/verify_release.py" in checks
    assert "release_tag: ${{ github.ref_name }}" in release
    assert "needs: checks" in release
    assert "id-token: write" not in checks
    assert "id-token: write" not in ci
    assert "id-token: write" in release
    assert "pypa/gh-action-pypi-publish@release/v1" in release
