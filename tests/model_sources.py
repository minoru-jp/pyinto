"""Source-level inspections cover every Construct module, not just its namespace."""

from __future__ import annotations

import ast
from pathlib import Path


def construct_trees() -> tuple[ast.Module, ...]:
    model_dir = Path(__file__).resolve().parents[1] / "src" / "pyinto" / "constructs"
    return tuple(
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(model_dir.glob("*.py"))
    )
