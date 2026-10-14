"""Target-independent values definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import ClassVar

from .base import Value
from .type_rules import _value_type_compatible
from .types import (
    ConstructError,
    Identifier,
    Symbol,
    ValueKind,
    ValueType,
)


@dataclass(frozen=True)
class Literal(Value):
    value: int | str

    def __post_init__(self) -> None:
        # Do not silently classify bool, float, or arbitrary objects as strings.
        # This is a Model-domain invariant, independent of any Target Pack.
        if type(self.value) not in (int, str):
            raise ValueError("Literal requires an integer or string value")

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"integer", "string"})

    def variant(self) -> str:
        return self.kind.value

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER if type(self.value) is int else ValueKind.STRING


@dataclass(frozen=True)
class FloatingLiteral(Value):
    """Python float literal, separate from the historical int/str Literal.

    The finite literal payload has binary floating-point value semantics. The
    Target Realization must honor the required arithmetic behavior and must
    reject the Model if it cannot do so; no numeric Interface is implied.
    """

    value: float

    def __post_init__(self) -> None:
        if type(self.value) is not float or not isfinite(self.value):
            raise ConstructError("FloatingLiteral requires a finite float")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.FLOAT


@dataclass(frozen=True)
class BooleanLiteral(Value):
    """Explicit Boolean constant, distinct from the int/str Literal contract."""

    value: bool

    def __post_init__(self) -> None:
        if type(self.value) is not bool:
            raise ConstructError("BooleanLiteral requires True or False")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"true", "false"})

    def variant(self) -> str:
        return "true" if self.value else "false"


@dataclass(frozen=True)
class NoneLiteral(Value):
    """The None singleton as a first-class expression, not a missing child."""

    @property
    def kind(self) -> ValueKind:
        return ValueKind.NONE


@dataclass(frozen=True)
class ConditionalExpression(Value):
    """Evaluate a Boolean condition once, then only the selected value branch.

    The result has a static declared shape. With no contextual type the
    Frontend requires identical branch shapes rather than inferring a union.
    The Realization must not eagerly evaluate both branches.
    """

    condition: Value
    when_true: Value
    when_false: Value
    result_type: ValueType
    HOLES: ClassVar[frozenset[str]] = frozenset(
        {"condition", "when_true", "when_false"}
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.condition, Value)
            or self.condition.kind is not ValueKind.BOOLEAN
        ):
            raise ConstructError("Conditional expression requires a Boolean condition")
        if not isinstance(self.result_type, ValueType):
            raise ConstructError("Conditional expression requires a result type")
        if not _value_type_compatible(
            self.result_type, self.when_true
        ) or not _value_type_compatible(self.result_type, self.when_false):
            raise ConstructError("Conditional expression branch type mismatch")

    @property
    def value_type(self) -> ValueType:
        return self.result_type

    def parts(self) -> Mapping[str, object]:
        return {
            "condition": self.condition,
            "when_true": self.when_true,
            "when_false": self.when_false,
        }


@dataclass(frozen=True)
class Reference(Value):
    symbol: Symbol
    HOLES: ClassVar[frozenset[str]] = frozenset({"name"})

    @property
    def kind(self) -> ValueKind:
        if self.symbol.kind is None:
            raise ConstructError("Callable cannot be used as a value")
        return self.symbol.kind

    @property
    def value_type(self) -> ValueType:
        return self.symbol.value_type

    def parts(self) -> Mapping[str, object]:
        return {"name": Identifier(self.symbol.name)}
