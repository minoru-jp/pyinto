"""Model symbol type storage after the modularization's third iteration."""

import pytest

from pyinto.constructs import (
    CallableType,
    ConstructError,
    InstanceType,
    MappedType,
    ParameterRole,
    Symbol,
    ValueKind,
    ValueType,
)


def test_symbol_owns_one_recursive_value_type() -> None:
    nominal = InstanceType("Node")
    result = ValueType(ValueKind.INSTANCE, instance_type=nominal)
    callback = CallableType((result,), result)
    declared = ValueType(ValueKind.FUNCTION, callable_type=callback)
    symbol = Symbol("callback", declared, declared.annotation())

    assert symbol.type is declared
    assert symbol.value_type is declared
    assert symbol.kind is ValueKind.FUNCTION
    assert symbol.callable_type is callback
    assert symbol.tuple_type is None
    assert symbol.mapped_type is None


def test_mapped_and_builtin_symbols_are_not_fabricated_value_types() -> None:
    mapped = MappedType("unit.memory", "integer")
    external = Symbol("memory", mapped, "unit.memory")
    built_in = Symbol("print", None)

    assert external.type is mapped
    assert external.mapped_type is mapped
    assert external.kind is ValueKind.MAPPED_OBJECT
    assert built_in.kind is None
    with pytest.raises(ConstructError, match="no ValueType"):
        _ = external.value_type
    with pytest.raises(ConstructError, match="no ValueType"):
        _ = built_in.value_type


def test_symbol_value_type_validation_stays_local_to_type() -> None:
    nominal = InstanceType("Item")
    receiver_type = ValueType(ValueKind.INSTANCE, instance_type=nominal)
    receiver = Symbol("current", receiver_type, "Item", role=ParameterRole.RECEIVER)
    assert receiver.instance_type == nominal
    assert receiver.value_type is receiver_type
    with pytest.raises(ValueError, match="Receiver"):
        Symbol(
            "invalid", ValueType(ValueKind.INTEGER), "int", role=ParameterRole.RECEIVER
        )
    with pytest.raises(ConstructError, match="callable shape"):
        ValueType(ValueKind.FUNCTION)
    with pytest.raises(ValueError, match="explicit type annotation"):
        Symbol("untyped", ValueType(ValueKind.INTEGER))
