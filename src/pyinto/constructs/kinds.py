"""Constructs for the ``pyinto.kinds`` vocabulary.

The Host gives these no execution meaning and attaches no semantic admission
obligations. They record what the source wrote so that a Target can spell it.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from typing import ClassVar

from .base import Construct, Value
from .type_rules import _value_type_compatible, is_none_alias
from .types import (
    CLASS_LABELS,
    NONE_ALIASES,
    ConstructError,
    InstanceType,
    KindLabel,
    ListType,
    Symbol,
    ValueKind,
    ValueType,
)
from .values import Reference


def pointee(value_type: ValueType) -> ValueType | None:
    """The ``T`` of a ``Pointer[T]`` label, or None for any other type."""
    label = value_type.label
    if label is None or label.name != "Pointer" or len(label.arguments) != 1:
        return None
    target = label.arguments[0]
    return target if isinstance(target, ValueType) else None


def _labeled(item: object) -> bool:
    if isinstance(item, Symbol):
        return isinstance(item.type, ValueType) and item.type.label is not None
    if isinstance(item, Value):
        try:
            return item.value_type.label is not None
        except (NotImplementedError, ConstructError):
            return False
    return False


def _flatten(items: Iterator[object] | tuple[object, ...]) -> Iterator[object]:
    for item in items:
        if isinstance(item, (tuple, list)):
            yield from _flatten(tuple(item))
        else:
            yield item


def involves_kind_label(node: Construct) -> bool:
    """Whether a node or one of its direct operands carries a kind label.

    Python-semantics admission obligations do not apply to such operations:
    the Host does not know what a kind does on the Target side.
    """
    if _labeled(node):
        return True
    for part in _flatten(tuple(node.parts().values())):
        if _labeled(part):
            return True
        target = getattr(part, "symbol", None)
        if isinstance(part, Reference) and _labeled(target):
            return True
    for name in ("target", "symbol"):
        if _labeled(getattr(node, name, None)):
            return True
    return False


@dataclass(frozen=True)
class NoneAlias(Value):
    """A ``Void`` / ``Nil`` / ``Null`` value: ``None`` spelled as vocabulary."""

    name: str
    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"void", "nil", "null"})

    def __post_init__(self) -> None:
        if self.name not in NONE_ALIASES:
            raise ConstructError("NoneAlias requires Void, Nil or Null")

    @property
    def value_type(self) -> ValueType:
        return ValueType(ValueKind.NONE, label=KindLabel(self.name))

    def variant(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class NoneAliasComparison(Value):
    """``==`` / ``!=`` between a None-alias word and a kind-labeled value."""

    left: Value
    operator: str
    right: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"left", "op", "right"})

    def __post_init__(self) -> None:
        if self.operator not in {"==", "!="}:
            raise ConstructError("None-alias comparison supports only == and !=")
        if not isinstance(self.left, Value) or not isinstance(self.right, Value):
            raise ConstructError("None-alias comparison requires two values")
        left, right = self.left.value_type, self.right.value_type
        if not (
            (is_none_alias(left) and right.label is not None)
            or (is_none_alias(right) and left.label is not None)
        ):
            raise ConstructError(
                "None-alias comparison needs a Void/Nil/Null word and a "
                "kind-labeled value"
            )

    @property
    def kind(self) -> ValueKind:
        return ValueKind.BOOLEAN

    def parts(self) -> Mapping[str, object]:
        return {"left": self.left, "op": self.operator, "right": self.right}


@dataclass(frozen=True)
class AddressOf(Value):
    """``Pointer.address(x)``: a ``Pointer[type of x]`` value for a variable."""

    target: Reference
    HOLES: ClassVar[frozenset[str]] = frozenset({"target"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target, Reference)
            or self.target.symbol.mapped_type is not None
            or not isinstance(self.target.symbol.type, ValueType)
        ):
            raise ConstructError("Pointer.address requires a typed variable")

    @property
    def value_type(self) -> ValueType:
        target = self.target.value_type
        return ValueType(ValueKind.INTEGER, label=KindLabel("Pointer", (target,)))

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target}


@dataclass(frozen=True)
class PointerLoad(Value):
    """``Pointer.load(p)``: the ``T`` value read through a ``Pointer[T]``."""

    pointer: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"pointer"})

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pointer, Value)
            or pointee(self.pointer.value_type) is None
        ):
            raise ConstructError("Pointer.load requires a Pointer[T] value")

    @property
    def value_type(self) -> ValueType:
        target = pointee(self.pointer.value_type)
        assert target is not None
        return target

    def parts(self) -> Mapping[str, object]:
        return {"pointer": self.pointer}


@dataclass(frozen=True)
class PointerStore(Construct):
    """``Pointer.store(p, v)``: write ``v`` through a ``Pointer[T]``."""

    pointer: Value
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"pointer", "value"})

    def __post_init__(self) -> None:
        if not isinstance(self.pointer, Value):
            raise ConstructError("Pointer.store requires a Pointer[T] value")
        target = pointee(self.pointer.value_type)
        if target is None:
            raise ConstructError("Pointer.store requires a Pointer[T] value")
        if not isinstance(self.value, Value) or not _value_type_compatible(
            target, self.value
        ):
            raise ConstructError("Pointer.store value does not match Pointer[T]")

    def parts(self) -> Mapping[str, object]:
        return {"pointer": self.pointer, "value": self.value}


def class_label(name: str, implemented: tuple[InstanceType, ...] = ()) -> KindLabel:
    """The label recorded on a class for ``@Interface`` / ``@MixIn`` / ``@Implements``."""
    if name not in CLASS_LABELS:
        raise ConstructError(f"Unknown kind class label: {name!r}")
    if (name == "Implements") != bool(implemented):
        raise ConstructError("Implements requires one or more classes")
    return KindLabel(
        name,
        tuple(ValueType(ValueKind.INSTANCE, instance_type=t) for t in implemented),
    )


# --- Dynamic memory vocabulary ----------------------------------------------
#
# Shape (single value or ``Buffer[T]``) and ownership (``Owned`` / ``Shared``)
# travel as type labels, so one operation word (``release`` ...) suffices and
# each Target picks its own spelling from the handle's type.

OWNERSHIP_LABELS: frozenset[str] = frozenset({"Owned", "Shared"})


def buffer_type(element: ValueType) -> ValueType:
    """``Buffer[T]``: a run-time-length sequence, a Python list on the source side."""
    return ValueType(
        ValueKind.LIST,
        list_type=ListType(element),
        label=KindLabel("Buffer", (element,)),
    )


def owned_type(inner: ValueType) -> ValueType:
    """``Owned[X]``: the shape of ``X`` labeled with ownership."""
    return replace(inner, label=KindLabel("Owned", (inner,)))


def owned_inner(value_type: ValueType) -> ValueType | None:
    """The ``X`` of an ``Owned[X]`` / ``Shared[X]`` label, else None."""
    label = value_type.label
    if label is None or label.name not in OWNERSHIP_LABELS:
        return None
    inner = label.arguments[0] if label.arguments else None
    return inner if isinstance(inner, ValueType) else None


def buffer_element(value_type: ValueType) -> ValueType | None:
    """The ``T`` of ``Buffer[T]``, also through ``Owned`` / ``Shared``."""
    inner = owned_inner(value_type) or value_type
    label = inner.label
    if label is None or label.name != "Buffer" or not label.arguments:
        return None
    element = label.arguments[0]
    return element if isinstance(element, ValueType) else None


def _handle(value: object, word: str) -> ValueType:
    if not isinstance(value, Value):
        raise ConstructError(f"Memory.{word} requires a value")
    return value.value_type


def _owned_handle(value: object, word: str) -> ValueType:
    inner = owned_inner(_handle(value, word))
    if inner is None:
        raise ConstructError(f"Memory.{word} requires an Owned or Shared value")
    return inner


def _integer(value: object, word: str) -> None:
    if not isinstance(value, Value) or value.kind is not ValueKind.INTEGER:
        raise ConstructError(f"Memory.{word} requires an integer length")


@dataclass(frozen=True)
class MemoryNew(Value):
    """``Memory.new(T, value)``: an ``Owned[T]`` single value."""

    element_type: ValueType
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"type", "value"})

    def __post_init__(self) -> None:
        if not isinstance(self.element_type, ValueType) or self.element_type.kind is (
            ValueKind.NONE
        ):
            raise ConstructError("Memory.new requires a value type")
        if not isinstance(self.value, Value) or not _value_type_compatible(
            self.element_type, self.value
        ):
            raise ConstructError("Memory.new value does not match its type")

    @property
    def value_type(self) -> ValueType:
        return owned_type(self.element_type)

    def parts(self) -> Mapping[str, object]:
        return {"type": self.element_type, "value": self.value}


@dataclass(frozen=True)
class MemoryNewBuffer(Value):
    """``Memory.new_buffer(T, length, value)``: an ``Owned[Buffer[T]]``."""

    element_type: ValueType
    length: Value
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"type", "length", "value"})

    def __post_init__(self) -> None:
        if not isinstance(self.element_type, ValueType) or self.element_type.kind is (
            ValueKind.NONE
        ):
            raise ConstructError("Memory.new_buffer requires a value type")
        _integer(self.length, "new_buffer")
        if not isinstance(self.value, Value) or not _value_type_compatible(
            self.element_type, self.value
        ):
            raise ConstructError("Memory.new_buffer value does not match its type")

    @property
    def value_type(self) -> ValueType:
        return owned_type(buffer_type(self.element_type))

    def parts(self) -> Mapping[str, object]:
        return {"type": self.element_type, "length": self.length, "value": self.value}


@dataclass(frozen=True)
class MemoryRelease(Construct):
    """``Memory.release(h)``: the end of an owned value's lifetime."""

    handle: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"handle"})
    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"single", "buffer"})

    def __post_init__(self) -> None:
        _owned_handle(self.handle, "release")

    def variant(self) -> str:
        return "buffer" if buffer_element(self.handle.value_type) else "single"

    def parts(self) -> Mapping[str, object]:
        return {"handle": self.handle}


@dataclass(frozen=True)
class MemoryResize(Construct):
    """``Memory.resize(h, length)``: change an owned buffer's length."""

    target: Reference
    length: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"target", "length"})

    def __post_init__(self) -> None:
        if not isinstance(self.target, Reference):
            raise ConstructError("Memory.resize requires a variable")
        _owned_handle(self.target, "resize")
        if buffer_element(self.target.value_type) is None:
            raise ConstructError("Memory.resize requires an owned Buffer")
        _integer(self.length, "resize")

    def parts(self) -> Mapping[str, object]:
        return {"target": self.target, "length": self.length}


@dataclass(frozen=True)
class MemoryLength(Value):
    """``Memory.length(h)``: the length of a ``Buffer``."""

    handle: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"handle"})

    def __post_init__(self) -> None:
        if buffer_element(_handle(self.handle, "length")) is None:
            raise ConstructError("Memory.length requires a Buffer")

    @property
    def kind(self) -> ValueKind:
        return ValueKind.INTEGER

    def parts(self) -> Mapping[str, object]:
        return {"handle": self.handle}


@dataclass(frozen=True)
class MemoryBorrow(Value):
    """``Memory.borrow(h)``: a non-owning view of an owned value.

    A single ``Owned[T]`` yields ``Pointer[T]``; ``Owned[Buffer[T]]`` yields the
    unowned ``Buffer[T]``.
    """

    handle: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"handle"})
    VARIANTS: ClassVar[frozenset[str] | None] = frozenset({"single", "buffer"})

    def __post_init__(self) -> None:
        _owned_handle(self.handle, "borrow")

    @property
    def value_type(self) -> ValueType:
        inner = owned_inner(self.handle.value_type)
        assert inner is not None
        element = buffer_element(inner)
        if element is not None:
            return buffer_type(element)
        return ValueType(ValueKind.INTEGER, label=KindLabel("Pointer", (inner,)))

    def variant(self) -> str:
        return "buffer" if buffer_element(self.handle.value_type) else "single"

    def parts(self) -> Mapping[str, object]:
        return {"handle": self.handle}


@dataclass(frozen=True)
class MemoryCopy(Construct):
    """``Memory.copy(destination, source)`` between two ``Buffer`` values."""

    destination: Value
    source: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"destination", "source"})

    def __post_init__(self) -> None:
        target = buffer_element(_handle(self.destination, "copy"))
        origin = buffer_element(_handle(self.source, "copy"))
        if target is None or origin is None:
            raise ConstructError("Memory.copy requires two Buffer values")
        if target != origin:
            raise ConstructError("Memory.copy requires matching element types")

    def parts(self) -> Mapping[str, object]:
        return {"destination": self.destination, "source": self.source}


@dataclass(frozen=True)
class MemoryFill(Construct):
    """``Memory.fill(h, value)``: set every element of a ``Buffer``."""

    handle: Value
    value: Value
    HOLES: ClassVar[frozenset[str]] = frozenset({"handle", "value"})

    def __post_init__(self) -> None:
        element = buffer_element(_handle(self.handle, "fill"))
        if element is None:
            raise ConstructError("Memory.fill requires a Buffer")
        if not isinstance(self.value, Value) or not _value_type_compatible(
            element, self.value
        ):
            raise ConstructError("Memory.fill value does not match the element type")

    def parts(self) -> Mapping[str, object]:
        return {"handle": self.handle, "value": self.value}
