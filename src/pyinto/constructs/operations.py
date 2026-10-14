"""Target-independent operations definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from .base import Value
from .control import Range
from .types import ConstructError, ValueKind, ValueType


@dataclass(frozen=True)
class Comparison(Value):
    left: Value
    operator: str
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "op", "right"})

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def __post_init__(self) -> None:
        if (
            self.left.kind is not ValueKind.INTEGER
            or self.right.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("Comparison requires integers")
        if self.operator not in {"<", "<=", ">", ">=", "==", "!="}:
            raise ConstructError(f"Unsupported comparison {self.operator!r}")

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "op": self.operator, "right": self.right}


@dataclass(frozen=True)
class ComparisonChain(Value):
    """Pairwise comparisons with one evaluation of each visited operand.

    Evaluation proceeds left to right. Stop at the first false comparison;
    do not evaluate remaining operands. An intermediate operand is reused
    between the two adjacent comparisons, never re-evaluated. This is NOT a
    BooleanOperation wrapping independent binary Comparisons.
    """

    operands: tuple[Value, ...]
    operators: tuple[str, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"operands", "operators"})

    def __post_init__(self) -> None:
        if len(self.operands) < 3 or len(self.operators) != len(self.operands) - 1:
            raise ConstructError(
                "ComparisonChain needs at least three operands and matching operators"
            )
        if any(op not in {"<", "<=", ">", ">=", "==", "!="} for op in self.operators):
            raise ConstructError("Unsupported chained comparison operator")
        if any(not isinstance(item, Value) for item in self.operands):
            raise ConstructError("Chained comparison operands must be Values")
        kind = self.operands[0].kind
        if kind not in {ValueKind.INTEGER, ValueKind.FLOAT, ValueKind.STRING} or any(
            item.kind is not kind for item in self.operands[1:]
        ):
            raise ConstructError("ComparisonChain requires one matching scalar type")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"operands": self.operands, "operators": self.operators}


@dataclass(frozen=True)
class Arithmetic(Value):
    """Integer arithmetic without choosing Target operator semantics.

    Operations retain source order and must be realized by a suitable Target;
    floor division/modulo and arbitrary-precision bitwise operations may need
    more than the corresponding fixed-width Target operators. Negative shifts
    and signed right shifts have Python-integer semantics, not C semantics.
    """

    left: Value
    operator: str
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "op", "right"})

    def __post_init__(self) -> None:
        if self.operator not in {"+", "-", "*", "//", "%", "&", "|", "^", "<<", ">>"}:
            raise ConstructError(f"Unsupported arithmetic operator {self.operator!r}")
        if (
            self.left.kind is not ValueKind.INTEGER
            or self.right.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("Arithmetic requires integer operands")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "op": self.operator, "right": self.right}


@dataclass(frozen=True)
class IntegerTrueDivision(Value):
    """True division of two integers, producing a floating-point Value.

    Each integer operand is evaluated once, left to right. This is the
    Python-style numeric contract: true division converts to float, can
    raise ZeroDivisionError on a zero divisor or OverflowError during float
    conversion, and is not integer truncation or floor division. No Target
    floating implementation or constant folding is selected by the Model.
    """

    left: Value
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "right"})

    def __post_init__(self) -> None:
        if (
            self.left.kind is not ValueKind.INTEGER
            or self.right.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("IntegerTrueDivision requires two integers")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.FLOAT

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "right": self.right}


@dataclass(frozen=True)
class FloatingArithmetic(Value):
    """Typed floating + - * /, with both operands evaluated in source order.

    Python float arithmetic is retained at the semantic level (including
    floating-point rounding and division-by-zero behavior); the Frontend
    never folds or executes the expression. A Target implementation must
    reproduce that behavior or decline realization.
    """

    left: Value
    operator: str
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "op", "right"})

    def __post_init__(self) -> None:
        if self.operator not in {"+", "-", "*", "/"}:
            raise ConstructError("Unsupported floating arithmetic operator")
        if (
            self.left.kind is not ValueKind.FLOAT
            or self.right.kind is not ValueKind.FLOAT
        ):
            raise ConstructError("Floating arithmetic requires float operands")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.FLOAT

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "op": self.operator, "right": self.right}


@dataclass(frozen=True)
class FloatingUnary(Value):
    """Typed floating unary +/-, preserving the operand as a Value."""

    operator: str
    operand: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"op", "operand"})

    def __post_init__(self) -> None:
        if self.operator not in {"+", "-"} or self.operand.kind is not ValueKind.FLOAT:
            raise ConstructError("Floating unary requires +/- and a float operand")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.FLOAT

    def parts(self) -> Mapping[str, object]:
        return {"op": self.operator, "operand": self.operand}


@dataclass(frozen=True)
class FloatingComparison(Value):
    """Order/equality comparison of float values, retaining Python NaN rules."""

    left: Value
    operator: str
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "op", "right"})

    def __post_init__(self) -> None:
        if self.operator not in {"<", "<=", ">", ">=", "==", "!="}:
            raise ConstructError("Unsupported floating comparison operator")
        if (
            self.left.kind is not ValueKind.FLOAT
            or self.right.kind is not ValueKind.FLOAT
        ):
            raise ConstructError("Floating comparison requires float operands")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "op": self.operator, "right": self.right}


@dataclass(frozen=True)
class StringConcat(Value):
    """Unicode string concatenation; each operand is evaluated once."""

    left: Value
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "right"})

    def __post_init__(self) -> None:
        if (
            self.left.kind is not ValueKind.STRING
            or self.right.kind is not ValueKind.STRING
        ):
            raise ConstructError("String concatenation requires two strings")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.STRING

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "right": self.right}


@dataclass(frozen=True)
class StringRepeat(Value):
    """A string repeated an integer number of times, either operand order."""

    left: Value
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "right"})

    def __post_init__(self) -> None:
        if (self.left.kind, self.right.kind) not in {
            (ValueKind.STRING, ValueKind.INTEGER),
            (ValueKind.INTEGER, ValueKind.STRING),
        }:
            raise ConstructError("String repetition requires str and int")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.STRING

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "right": self.right}


@dataclass(frozen=True)
class StringComparison(Value):
    """Lexicographic Unicode-code-point comparison of two strings."""

    left: Value
    operator: str
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "op", "right"})

    def __post_init__(self) -> None:
        if self.operator not in {"<", "<=", ">", ">=", "==", "!="}:
            raise ConstructError("Unsupported string comparison operator")
        if (
            self.left.kind is not ValueKind.STRING
            or self.right.kind is not ValueKind.STRING
        ):
            raise ConstructError("String comparison requires string operands")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "op": self.operator, "right": self.right}


@dataclass(frozen=True)
class StringContains(Value):
    """Substring membership in a typed string; no arbitrary object protocol."""

    needle: Value
    haystack: Value
    negate: bool = False
    HOLES: ClassVar[frozenset[str]] = frozenset({"needle", "haystack"})

    def __post_init__(self) -> None:
        if (
            self.needle.kind is not ValueKind.STRING
            or self.haystack.kind is not ValueKind.STRING
        ):
            raise ConstructError("String membership requires two strings")
        if type(self.negate) is not bool:
            raise ConstructError("String membership negation must be Boolean")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"needle": self.needle, "haystack": self.haystack}

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"in", "not_in"})

    def variant(self) -> str:
        return "not_in" if self.negate else "in"


@dataclass(frozen=True)
class StringElement(Value):
    """One Unicode code point at an integer index (including negative indices).

    Out-of-range indexing raises IndexError. Slicing and string mutation are
    not part of this new operation.
    """

    source: Value
    index: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"source", "index"})

    def __post_init__(self) -> None:
        if (
            self.source.kind is not ValueKind.STRING
            or self.index.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("String indexing requires str and int")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.STRING

    def parts(self) -> Mapping[str, object]:
        return {"source": self.source, "index": self.index}


@dataclass(frozen=True)
class Length(Value):
    """Length of a typed str/tuple/list/dict, evaluated at its use site.

    For mutable collections the result reflects their current element count;
    dictionary length counts distinct keys. A Target must preserve Unicode
    code-point length for strings, rather than assuming byte length.
    """

    operand: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"operand"})

    def __post_init__(self) -> None:
        if not isinstance(self.operand, Value) or self.operand.kind not in {
            ValueKind.STRING,
            ValueKind.TUPLE,
            ValueKind.LIST,
            ValueKind.DICT,
        }:
            raise ConstructError("Length requires a typed str, tuple, list or dict")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"operand": self.operand}


@dataclass(frozen=True)
class Absolute(Value):
    """Absolute value of a typed integer; Target integer bounds are not fixed."""

    operand: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"operand"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operand, Value)
            or self.operand.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("Absolute requires a typed integer")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"operand": self.operand}


@dataclass(frozen=True)
class Extremum(Value):
    """Integer min/max of 2+ expressions, evaluated once in source order."""

    operation: str
    operands: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"operation", "operands"})

    def __post_init__(self) -> None:
        if self.operation not in {"min", "max"}:
            raise ConstructError("Extremum operation must be min or max")
        if len(self.operands) < 2 or any(
            not isinstance(value, Value) or value.kind is not ValueKind.INTEGER
            for value in self.operands
        ):
            raise ConstructError("Extremum requires at least two typed integers")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"operation": self.operation, "operands": self.operands}


@dataclass(frozen=True)
class IntegerSum(Value):
    """Ordered integer aggregation of a typed collection or integer range.

    The source collection (and optional starting integer) is evaluated once;
    the elements are then traversed in order, without frontend folding.
    Mutable lists are read at the operation's evaluation time. The default
    start is the integer zero, not an absent or untyped result.
    """

    iterable: Value
    start: Value | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"iterable", "start"})

    def __post_init__(self) -> None:
        if not isinstance(self.iterable, Value) or not _integer_aggregation_source(
            self.iterable
        ):
            raise ConstructError(
                "IntegerSum requires list[int], tuple of ints or Range"
            )
        if self.start is not None and (
            not isinstance(self.start, Value)
            or self.start.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("IntegerSum start requires a typed integer")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        result: dict[str, object] = {"iterable": self.iterable}
        if self.start is not None:
            result["start"] = self.start
        return result


def _integer_aggregation_source(source: Value) -> bool:
    if isinstance(source, Range):
        return True
    if source.kind is ValueKind.LIST:
        shape = source.list_type
        return shape is not None and shape.element_type == ValueType(ValueKind.INTEGER)
    if source.kind is ValueKind.TUPLE:
        shape = source.tuple_type
        return shape is not None and (
            shape.variadic_element_type == ValueType(ValueKind.INTEGER)
            if shape.variadic_element_type is not None
            else all(
                part == ValueType(ValueKind.INTEGER) for part in shape.element_types
            )
        )
    return False


@dataclass(frozen=True)
class BooleanAggregate(Value):
    """Short-circuit any/all over a typed Boolean list or fixed tuple.

    ``any`` stops at its first true element and yields false when empty;
    ``all`` stops at its first false element and yields true when empty.
    The iterable expression is evaluated once, and item truthiness coercion
    (including user-defined ``__bool__``) is intentionally not adopted.
    """

    operation: str
    iterable: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"operation", "iterable"})

    def __post_init__(self) -> None:
        if self.operation not in {"any", "all"}:
            raise ConstructError("BooleanAggregate operation must be any or all")
        if not isinstance(self.iterable, Value) or not _boolean_aggregation_source(
            self.iterable
        ):
            raise ConstructError(
                "BooleanAggregate requires list[bool] or tuple of bools"
            )

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"operation": self.operation, "iterable": self.iterable}


def _boolean_aggregation_source(source: Value) -> bool:
    if source.kind is ValueKind.LIST:
        shape = source.list_type
        return shape is not None and shape.element_type == ValueType(ValueKind.BOOLEAN)
    if source.kind is ValueKind.TUPLE:
        shape = source.tuple_type
        return shape is not None and (
            shape.variadic_element_type == ValueType(ValueKind.BOOLEAN)
            if shape.variadic_element_type is not None
            else all(
                part == ValueType(ValueKind.BOOLEAN) for part in shape.element_types
            )
        )
    return False


@dataclass(frozen=True)
class IntegerUnary(Value):
    """Integer unary +/- or arbitrary-precision bitwise complement (~)."""

    operator: str
    operand: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"op", "operand"})

    def __post_init__(self) -> None:
        if self.operator not in {"+", "-", "~"}:
            raise ConstructError(
                f"Unsupported integer unary operator {self.operator!r}"
            )
        if self.operand.kind is not ValueKind.INTEGER:
            raise ConstructError("Integer unary operation requires an integer")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"op": self.operator, "operand": self.operand}


@dataclass(frozen=True)
class BooleanOperation(Value):
    """Source-order, short-circuit and/or over explicit Boolean operands.

    A Target Realization is responsible for conditional evaluation of each
    operand; the Model neither pre-evaluates nor flattens the expression.
    """

    operator: str
    operands: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"values", "op"})

    def __post_init__(self) -> None:
        if self.operator not in {"and", "or"}:
            raise ConstructError(f"Unsupported Boolean operator {self.operator!r}")
        if len(self.operands) < 2:
            raise ConstructError("Boolean operation requires at least two operands")
        if any(value.kind is not ValueKind.BOOLEAN for value in self.operands):
            raise ConstructError("Boolean operation requires Boolean operands")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"op": self.operator, "values": self.operands}


@dataclass(frozen=True)
class BooleanNot(Value):
    """Boolean negation over a structurally retained operand."""

    operand: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"operand"})

    def __post_init__(self) -> None:
        if self.operand.kind is not ValueKind.BOOLEAN:
            raise ConstructError("Boolean not requires a Boolean operand")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"operand": self.operand}
