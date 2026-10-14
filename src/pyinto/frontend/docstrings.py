"""Pure AST shape recognition for static declaration docstrings.

No docstring expression is evaluated and no __doc__ runtime protocol is
implemented by the Model.
"""

from __future__ import annotations

import ast


def split_docstring(body: list[ast.stmt]) -> tuple[str | None, list[ast.stmt]]:
    """Return only an initial literal string and the remaining statements."""
    if body and isinstance(body[0], ast.Expr):
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value, body[1:]
    return None, body
