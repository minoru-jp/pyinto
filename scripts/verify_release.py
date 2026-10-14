"""Fail unless the release tag identifies this checkout's declared version.

Usage: python scripts/verify_release.py v0.0.1
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(tag: str) -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    expected = f"v{project['version']}"
    if tag != expected:
        raise ValueError(f"Release tag {tag!r} does not match {expected!r}")
    print(f"Release tag matches project version: {expected}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "Usage: python scripts/verify_release.py v<project-version>",
            file=sys.stderr,
        )
        return 2
    try:
        verify(argv[1])
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
