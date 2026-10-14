"""Check pyinto's distributable files without importing their source tree.

Usage: python scripts/verify_dist.py dist
"""

from __future__ import annotations

import sys
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(directory: Path) -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    name, version = project["name"], project["version"]
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Expected exactly one wheel and one source distribution")
    wheel, sdist = wheels[0], sdists[0]
    if wheel.name != f"{name}-{version}-py3-none-any.whl":
        raise ValueError(f"Unexpected wheel name: {wheel.name}")
    if sdist.name != f"{name}-{version}.tar.gz":
        raise ValueError(f"Unexpected sdist name: {sdist.name}")

    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
        metadata_path = f"{name}-{version}.dist-info/METADATA"
        if metadata_path not in members:
            raise ValueError("Wheel is missing distribution metadata")
        metadata = Parser().parsestr(archive.read(metadata_path).decode("utf-8"))
        if metadata.get("Name") != name or metadata.get("Version") != version:
            raise ValueError("Wheel metadata does not match project name/version")
        description = metadata.get_payload()
        if not isinstance(description, str) or "Host" not in description:
            raise ValueError("Wheel metadata does not contain the English README")
        if "pyinto/__init__.py" not in members:
            raise ValueError("Wheel is missing the Host package")
        if any(
            member.startswith(("pyinto/targets/", "pyinto/contracts/", "tests/"))
            for member in members
        ):
            raise ValueError("Wheel contains an excluded Target or development asset")

    with tarfile.open(sdist, "r:gz") as archive:
        members = {item.name for item in archive.getmembers()}
        prefix = f"{name}-{version}/"
        required = (
            "README.md",
            "LICENSE",
            "pyproject.toml",
            "docs/GLOSSARY.md",
            "docs/specification/INDEX.md",
            "docs/target_implementation/INDEX.md",
            "src/pyinto/__init__.py",
        )
        missing = [item for item in required if prefix + item not in members]
        if missing:
            raise ValueError("sdist is missing: " + ", ".join(missing))
    print(
        f"Verified Host-only wheel and source distribution: {wheel.name}, {sdist.name}"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python scripts/verify_dist.py DIST_DIR", file=sys.stderr)
        return 2
    try:
        verify(Path(argv[1]))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
