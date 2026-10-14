"""Host-owned Builtins Interface: currently normalized builtin operations.

These classes are the Model-facing Construct exports, not replacements for
Python builtins. Python source continues to execute ordinary Python builtins.
The full Python builtins catalog is a source-level classification, not a claim
that every entry has a normalized Construct or Target Realization.
"""

from dataclasses import dataclass

from pyinto.constructs import (
    Absolute,
    BooleanAggregate,
    Extremum,
    IntegerSum,
    Length,
    PrintValues,
    Range,
)


@dataclass(frozen=True)
class _BuiltinCallElement:
    """Identity of a currently normalized direct builtin Call, not a renderer."""

    name: str


# Direct single-string print is still a Call; PrintValues is a different
# Construct with different argument semantics. Keep those subjects distinct.
PrintCall = _BuiltinCallElement("print")


__all__ = [
    "Absolute",
    "BooleanAggregate",
    "Extremum",
    "IntegerSum",
    "Length",
    "PrintCall",
    "PrintValues",
    "Range",
]
