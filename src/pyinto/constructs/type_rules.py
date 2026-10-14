"""Target-independent, explicitly limited type compatibility decisions."""

from __future__ import annotations

from .base import Value
from .types import Symbol, ValueKind, ValueType


def assignable(expected: ValueType, actual: ValueType) -> bool:
    """Can a value with ``actual`` type inhabit ``expected``?

    Only nominal instance subtyping and the preexisting top kinds (Any,
    object) are accepted. Recursive collection and Callable shapes stay
    invariant; declaration/signature equality remains a separate decision.
    """
    if expected.kind in (ValueKind.ANY, ValueKind.OBJECT):
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


def _value_type_compatible(expected: ValueType, actual: Value) -> bool:
    if not isinstance(actual, Value) or actual.kind is ValueKind.PORT_OBJECT:
        return False
    return assignable(expected, actual.value_type)


def _compatible(symbol: Symbol, value: Value) -> bool:
    """Ordinary value assignability, or the independent Port identity rule."""
    from .values import Reference

    if symbol.kind in (ValueKind.ANY, ValueKind.OBJECT):
        return True
    if symbol.kind is ValueKind.PORT_OBJECT:
        return (
            isinstance(value, Reference)
            and symbol.port_type is not None
            and symbol.port_type == value.symbol.port_type
        )
    if symbol.kind is None:
        return False
    return _value_type_compatible(symbol.value_type, value)
