"""Shared diagnostic type for unsupported Python syntax and declarations."""

from __future__ import annotations

import ast


class UnsupportedPython(ValueError):
    """Input cannot be normalized without guessing missing declarations."""


def reject(node: ast.AST, reason: str) -> UnsupportedPython:
    return UnsupportedPython(
        f"line {getattr(node, 'lineno', '?')}: {reason} ({type(node).__name__})"
    )
