"""Target-independent collections definitions for the pyinto Construct Model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from .base import Construct, Value
from .type_rules import _value_type_compatible
from .types import (
    ConstructError,
    DictType,
    ListType,
    TupleType,
    ValueKind,
    ValueType,
)
from .values import Literal, Reference


@dataclass(frozen=True)
class TupleValue(Value):
    """Fixed-arity tuple; items remain ordered expressions, not evaluated data."""

    items: tuple[Value, ...]
    HOLES: ClassVar[frozenset[str]] = frozenset({"items"})

    def __post_init__(self) -> None:
        if any(not isinstance(item, Value) for item in self.items):
            raise ConstructError("Tuple items must be Values")
        if any(
            item.kind in {ValueKind.MAPPED_OBJECT, ValueKind.NONE}
            for item in self.items
        ):
            raise ConstructError("Tuple items require supported value types")

    @property
    def value_type(self) -> ValueType:
        return ValueType(
            ValueKind.TUPLE,
            tuple_type=TupleType(tuple(item.value_type for item in self.items)),
        )

    def parts(self) -> Mapping[str, object]:
        return {"items": self.items}


@dataclass(frozen=True)
class TupleElement(Value):
    """Statically indexed element of a typed fixed tuple, with no dynamic lookup."""

    source: Value
    index: int
    HOLES: ClassVar[frozenset[str]] = frozenset({"source", "index"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source, Value)
            or self.source.kind is not ValueKind.TUPLE
        ):
            raise ConstructError("Tuple element access requires a tuple Value")
        shape = self.source.tuple_type
        if shape is None or shape.variadic_element_type is not None:
            raise ConstructError(
                "Fixed tuple element access requires a fixed tuple shape"
            )
        if type(self.index) is not int or not 0 <= self.index < len(
            shape.element_types
        ):
            raise ConstructError("Tuple element index must be a valid static position")

    @property
    def value_type(self) -> ValueType:
        shape = self.source.tuple_type
        assert shape is not None
        return shape.element_types[self.index]

    def parts(self) -> Mapping[str, object]:
        return {"source": self.source, "index": Literal(self.index)}


@dataclass(frozen=True)
class ListValue(Value):
    """Typed homogeneous list creation. Order and mutable identity are retained."""

    items: tuple[Value, ...]
    element_type: ValueType
    HOLES: ClassVar[frozenset[str]] = frozenset({"items"})

    def __post_init__(self) -> None:
        ListType(self.element_type)  # Validate independently of the Frontend.
        if any(not isinstance(item, Value) for item in self.items):
            raise ConstructError("List items must be Values")
        if any(
            not _value_type_compatible(self.element_type, item) for item in self.items
        ):
            raise ConstructError("List element type mismatch")

    @property
    def value_type(self) -> ValueType:
        return ValueType(ValueKind.LIST, list_type=ListType(self.element_type))

    def parts(self) -> Mapping[str, object]:
        return {"items": self.items}


@dataclass(frozen=True)
class SliceValue(Value):
    """A typed sequence slice retaining *omitted* bounds separately from values.

    Source then present lower/upper/step expressions are evaluated once, in
    that order. Python-style slicing handles negative indices, clipping, and
    signed steps; a zero step raises ValueError at runtime. A list slice makes
    a distinct outer list while retaining element references (shallow copy).
    A string slice selects Unicode code points. No slicing is executed here.
    """

    source: Value
    start: Value | None = None
    stop: Value | None = None
    step: Value | None = None
    HOLES: ClassVar[frozenset[str]] = frozenset({"source", "start", "stop", "step"})

    def __post_init__(self) -> None:
        if not isinstance(self.source, Value) or self.source.kind not in {
            ValueKind.LIST,
            ValueKind.STRING,
        }:
            raise ConstructError("Slice source requires a typed list or string Value")
        for name in ("start", "stop", "step"):
            bound = getattr(self, name)
            if bound is not None and (
                not isinstance(bound, Value) or bound.kind is not ValueKind.INTEGER
            ):
                raise ConstructError(
                    f"Slice {name} requires an integer Value or omission"
                )

    @property
    def value_type(self) -> ValueType:
        # A slice preserves its source type, not the list's *identity*.
        return self.source.value_type

    def parts(self) -> Mapping[str, object]:
        parts: dict[str, object] = {"source": self.source}
        for name in ("start", "stop", "step"):
            bound = getattr(self, name)
            if bound is not None:
                parts[name] = bound
        return parts

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"list", "string"})

    def variant(self) -> str:
        return "list" if self.kind is ValueKind.LIST else "string"


@dataclass(frozen=True)
class ListElement(Value):
    """Read an indexed list element, preserving the index expression."""

    source: Value
    index: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"source", "index"})

    def __post_init__(self) -> None:
        if not isinstance(self.source, Value) or self.source.kind is not ValueKind.LIST:
            raise ConstructError("List element access requires a list Value")
        if self.source.list_type is None:
            raise ConstructError("List element access requires a known element type")
        if (
            not isinstance(self.index, Value)
            or self.index.kind is not ValueKind.INTEGER
        ):
            raise ConstructError("List element index must be an integer Value")

    @property
    def value_type(self) -> ValueType:
        shape = self.source.list_type
        assert shape is not None
        return shape.element_type

    def parts(self) -> Mapping[str, object]:
        return {"source": self.source, "index": self.index}


@dataclass(frozen=True)
class ListElementAssign(Construct):
    """Mutate an element of an existing list binding, not its name binding."""

    target: Reference
    index: Value
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"target", "index", "value"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target, Reference)
            or self.target.kind is not ValueKind.LIST
        ):
            raise ConstructError("List element assignment requires a list Reference")
        if (
            not isinstance(self.index, Value)
            or self.index.kind is not ValueKind.INTEGER
        ):
            raise ConstructError(
                "List element assignment index must be an integer Value"
            )
        shape = self.target.list_type
        if shape is None or not _value_type_compatible(shape.element_type, self.value):
            raise ConstructError("List element assignment type mismatch")

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target, "index": self.index, "value": self.value}


@dataclass(frozen=True)
class DictEntry(Construct):
    """An ordered dictionary literal entry, preserving key/value expressions."""

    key: Value
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"key", "value"})

    def __post_init__(self) -> None:
        if not isinstance(self.key, Value) or not isinstance(self.value, Value):
            raise ConstructError("Dict entry requires key and value Values")

    def parts(self) -> Mapping[str, object]:
        return {"key": self.key, "value": self.value}


@dataclass(frozen=True)
class DictValue(Value):
    """Typed mutable dictionary expression, retaining all entries in source order.

    Inserting an existing equal key replaces its value but not its position.
    Each key and value expression is evaluated once in source order; alias
    bindings of the resulting map share the same mutable identity.
    """

    entries: tuple[DictEntry, ...]
    key_type: ValueType
    element_type: ValueType
    HOLES: ClassVar[frozenset[str]] = frozenset({"entries"})

    def __post_init__(self) -> None:
        DictType(self.key_type, self.element_type)
        if any(not isinstance(entry, DictEntry) for entry in self.entries):
            raise ConstructError("Dict entries must be DictEntry objects")
        if any(
            not _value_type_compatible(self.key_type, entry.key)
            or not _value_type_compatible(self.element_type, entry.value)
            for entry in self.entries
        ):
            raise ConstructError("Dict entry type mismatch")

    @property
    def value_type(self) -> ValueType:
        return ValueType(
            ValueKind.DICT, dict_type=DictType(self.key_type, self.element_type)
        )

    def parts(self) -> Mapping[str, object]:
        return {"entries": self.entries}


@dataclass(frozen=True)
class DictElement(Value):
    """Read a dictionary entry, with a runtime missing-key failure contract."""

    source: Value
    key: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"source", "key"})

    def __post_init__(self) -> None:
        if not isinstance(self.source, Value) or self.source.kind is not ValueKind.DICT:
            raise ConstructError("Dict access requires a dict Value")
        shape = self.source.dict_type
        if shape is None or not _value_type_compatible(shape.key_type, self.key):
            raise ConstructError("Dict lookup key type mismatch")

    @property
    def value_type(self) -> ValueType:
        shape = self.source.dict_type
        assert shape is not None
        return shape.value_type

    def parts(self) -> Mapping[str, object]:
        return {"source": self.source, "key": self.key}


@dataclass(frozen=True)
class DictElementAssign(Construct):
    """Insert or replace one entry of a typed dictionary binding."""

    target: Reference
    key: Value
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"target", "key", "value"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target, Reference)
            or self.target.kind is not ValueKind.DICT
        ):
            raise ConstructError("Dict update requires a dict Reference")
        shape = self.target.dict_type
        if shape is None or not _value_type_compatible(shape.key_type, self.key):
            raise ConstructError("Dict update key type mismatch")
        if not _value_type_compatible(shape.value_type, self.value):
            raise ConstructError("Dict update value type mismatch")

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target, "key": self.key, "value": self.value}


@dataclass(frozen=True)
class Membership(Value):
    """Typed list element or dictionary-key membership with source ordering.

    The element is evaluated before the container, each exactly once. Lists
    test elements using Python's identity-or-equality membership behavior in
    iteration order; dictionaries test keys through hashing and equality, not
    values. The Model never performs a lookup during construction.
    """

    element: Value
    container: Value
    negate: bool = False
    HOLES: ClassVar[frozenset[str]] = frozenset({"element", "container"})

    def __post_init__(self) -> None:
        if not isinstance(self.element, Value) or not isinstance(self.container, Value):
            raise ConstructError("Membership operands must be Values")
        if type(self.negate) is not bool:
            raise ConstructError("Membership negation must be Boolean")
        if self.container.kind is ValueKind.LIST:
            shape = self.container.list_type
            if shape is None or not _value_type_compatible(
                shape.element_type, self.element
            ):
                raise ConstructError("List membership element type mismatch")
        elif self.container.kind is ValueKind.DICT:
            shape = self.container.dict_type
            if shape is None or not _value_type_compatible(
                shape.key_type, self.element
            ):
                raise ConstructError("Dict membership key type mismatch")
        else:
            raise ConstructError("Membership requires a typed list or dict")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"element": self.element, "container": self.container}

    VARIANTS: ClassVar[frozenset[str] | None] = frozenset(
        {"list_in", "list_not_in", "dict_in", "dict_not_in"}
    )

    def variant(self) -> str:
        collection = "list" if self.container.kind is ValueKind.LIST else "dict"
        return f"{collection}_{'not_in' if self.negate else 'in'}"
