"""Ordered Unicode string composition and typed standard output operations.

These are Model semantics, not Python/C rendering recipes. String conversions
are represented by typed IntrinsicCall children, not performed by the parser.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from .base import Construct, Value
from .types import ConstructError, ValueKind


@dataclass(frozen=True)
class FormattedString(Value):
    """Join string-valued fragments after evaluating them once, left to right.

    A formatted source expression is an explicit typed ``str`` IntrinsicCall
    child. No Target formatting algorithm is selected here. The first failing
    fragment prevents later fragments from being evaluated.
    """

    fragments: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"fragments"})

    def __post_init__(self) -> None:
        if not self.fragments or any(
            not isinstance(fragment, Value) or fragment.kind is not ValueKind.STRING
            for fragment in self.fragments
        ):
            raise ConstructError("FormattedString requires string Value fragments")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.STRING

    def parts(self) -> Mapping[str, object]:
        return {"fragments": self.fragments}


@dataclass(frozen=True)
class PrintValues(Construct):
    """Write stringified, space-separated values followed by a newline.

    The children are typed ``str`` conversion expressions. Input expressions
    must all be evaluated once in source order *before any output is written*.
    Zero arguments emit only a newline. Output failure/partial writes belong
    to the output operation contract, not the value conversion contract.
    """

    values: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"values"})

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, Value) or value.kind is not ValueKind.STRING
            for value in self.values
        ):
            raise ConstructError("PrintValues requires string Value arguments")

    def parts(self) -> Mapping[str, object]:
        return {"values": self.values}
