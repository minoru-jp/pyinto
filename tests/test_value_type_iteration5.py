"""Iteration 5: structural ValueType projections and call assignability."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    CallableType,
    ConstructError,
    FunctionCall,
    FunctionSignature,
    FunctionValueCall,
    InstanceType,
    ListElement,
    ListType,
    Literal,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.constructs.type_rules import assignable
from pyinto.frontend import PythonFrontend


def _typed(name: str, value_type: ValueType) -> Reference:
    return Reference(Symbol(name, value_type, value_type.annotation()))


def test_direct_and_indirect_calls_share_nominal_argument_subtyping() -> None:
    base = InstanceType("Base")
    derived = InstanceType("Derived", base=base)
    base_type = ValueType(ValueKind.INSTANCE, instance_type=base)
    derived_type = ValueType(ValueKind.INSTANCE, instance_type=derived)
    signature = FunctionSignature(
        "take",
        (Symbol("item", base_type, "Base"),),
        "int",
        ValueType(ValueKind.INTEGER),
    )
    argument = _typed("child", derived_type)

    direct = FunctionCall(signature, (argument,))
    indirect = FunctionValueCall(Reference(signature.value_symbol), (argument,))
    assert direct.value_type == indirect.value_type == signature.return_type
    assert assignable(base_type, derived_type)
    assert not assignable(derived_type, base_type)
    needs_child = FunctionSignature(
        "needs_child",
        (Symbol("child", derived_type, "Derived"),),
        "int",
        ValueType(ValueKind.INTEGER),
    )
    with pytest.raises(ConstructError, match="type mismatch"):
        FunctionValueCall(
            Reference(needs_child.value_symbol), (_typed("parent", base_type),)
        )


def test_nested_collection_and_callable_types_remain_invariant() -> None:
    base = InstanceType("Base")
    derived = InstanceType("Derived", base=base)
    root = ValueType(ValueKind.INSTANCE, instance_type=base)
    child = ValueType(ValueKind.INSTANCE, instance_type=derived)
    list_root = ValueType(ValueKind.LIST, list_type=ListType(root))
    list_child = ValueType(ValueKind.LIST, list_type=ListType(child))
    assert not assignable(list_root, list_child)
    assert not assignable(list_child, list_root)
    call_root = ValueType(ValueKind.FUNCTION, callable_type=CallableType((root,), root))
    call_child = ValueType(
        ValueKind.FUNCTION, callable_type=CallableType((child,), child)
    )
    assert not assignable(call_root, call_child)
    assert assignable(call_root, call_root)


def test_structural_value_type_is_reused_not_reassembled() -> None:
    item = ValueType(
        ValueKind.FUNCTION,
        callable_type=CallableType(
            (ValueType(ValueKind.INTEGER),), ValueType(ValueKind.INTEGER)
        ),
    )
    parent = ValueType(ValueKind.LIST, list_type=ListType(item))
    reference = _typed("items", parent)
    element = ListElement(reference, Literal(0))
    assert reference.value_type is parent
    assert reference.list_type == parent.list_type
    assert element.value_type is item
    assert element.callable_type is item.callable_type
    assert element.kind is ValueKind.FUNCTION
    assert element.tuple_type is None


def test_frontend_indirect_call_subtype_is_accepted() -> None:
    program = PythonFrontend().parse("""
from typing import Callable
class Base:
    def __init__(self) -> None:
        self.n: int = 1
class Derived(Base):
    def __init__(self) -> None:
        super().__init__()
        self.m: int = 2

def take(x: Base) -> int:
    return x.n

f: Callable[[Base], int] = take
v: int = f(Derived())
""")
    init = program.body.children[-1]
    assert isinstance(init.value, FunctionValueCall)  # type: ignore[attr-defined]
