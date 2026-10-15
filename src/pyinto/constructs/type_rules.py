"""Target-independent, explicitly limited type compatibility decisions."""

from __future__ import annotations

from .base import Value
from .types import NONE_ALIASES, Symbol, ValueKind, ValueType


def assignable(expected: ValueType, actual: ValueType) -> bool:
    """Can a value with ``actual`` type inhabit ``expected``?

    Only nominal instance subtyping and the preexisting top kinds (Any,
    object) are accepted. Recursive collection and Callable shapes stay
    invariant; declaration/signature equality remains a separate decision.
    """
    if expected.kind in (ValueKind.ANY, ValueKind.OBJECT):
        return True
    # Kind labels never decide compatibility (ValueType equality ignores
    # them). The one addition: a None-alias word (Void/Nil/Null) may inhabit
    # any declaration that itself carries a kind label.
    if is_none_alias(actual) and expected.label is not None:
        return True
    # A fixed tuple of compatible elements inhabits a homogeneous, arbitrary-
    # length tuple shape. No mutable collection covariance is inferred.
    if expected.kind is ValueKind.TUPLE and expected.tuple_type is not None:
        element = expected.tuple_type.variadic_element_type
        if element is not None and actual.kind is ValueKind.TUPLE:
            shape = actual.tuple_type
            return shape is not None and (
                assignable(element, shape.variadic_element_type)
                if shape.variadic_element_type is not None
                else all(assignable(element, item) for item in shape.element_types)
            )
    if expected.kind is ValueKind.INSTANCE:
        return (
            expected.instance_type is not None
            and actual.instance_type is not None
            and actual.instance_type.is_subtype_of(expected.instance_type)
        )
    return expected == actual


def is_none_alias(value_type: ValueType) -> bool:
    """A value spelled with one of the None-alias vocabulary words."""
    return (
        value_type.kind is ValueKind.NONE
        and value_type.label is not None
        and value_type.label.name in NONE_ALIASES
    )


def is_ref(value_type: ValueType | None) -> bool:
    return (
        value_type is not None
        and value_type.label is not None
        and value_type.label.name == "Ref"
    )


def _binds(symbol: Symbol, value: Value) -> bool:
    """Compatibility at a *binding* site (initializer, argument, default).

    A ``Ref[T]`` binding additionally requires the bound value to be a plain
    variable reference. Later assignments to the name use ``_compatible``.
    """
    from .values import Reference

    if not _compatible(symbol, value):
        return False
    return not is_ref(symbol.type if isinstance(symbol.type, ValueType) else None) or (
        isinstance(value, Reference) and value.symbol.mapped_type is None
    )


def _value_type_compatible(expected: ValueType, actual: Value) -> bool:
    if not isinstance(actual, Value) or actual.kind is ValueKind.MAPPED_OBJECT:
        return False
    return assignable(expected, actual.value_type)


def _compatible(symbol: Symbol, value: Value) -> bool:
    """Ordinary value assignability, or the independent mapped-type identity rule."""
    from .values import Reference

    if symbol.kind in (ValueKind.ANY, ValueKind.OBJECT):
        return True
    if symbol.kind is ValueKind.MAPPED_OBJECT:
        return (
            isinstance(value, Reference)
            and symbol.mapped_type is not None
            and symbol.mapped_type == value.symbol.mapped_type
        )
    if symbol.kind is None:
        return False
    return _value_type_compatible(symbol.value_type, value)
