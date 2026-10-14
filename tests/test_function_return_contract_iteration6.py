"""Iteration 6: function-owned return type invariants, without flow analysis."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pyinto.constructs import (
    Block,
    BooleanLiteral,
    Branch,
    Construct,
    ConstructError,
    ContextEntry,
    ExceptHandler,
    For,
    FunctionDefinition,
    FunctionSignature,
    InstanceType,
    IterationEntry,
    Literal,
    NoneLiteral,
    Range,
    Reference,
    Return,
    Symbol,
    Try,
    ValueKind,
    ValueType,
    While,
    With,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def _signature(return_type: ValueType, name: str = "f") -> FunctionSignature:
    return FunctionSignature(name, (), return_type.annotation(), return_type)


def _definition(return_type: ValueType, *statements: Construct) -> FunctionDefinition:
    return FunctionDefinition(_signature(return_type), Block(statements))


def test_cst_017_model_rejects_bad_return_without_frontend() -> None:
    integer = ValueType(ValueKind.INTEGER)
    with pytest.raises(ConstructError, match="return type mismatch"):
        _definition(integer, Return(Literal("not an integer")))
    with pytest.raises(ConstructError, match="return type mismatch"):
        _definition(integer, Return())
    assert _definition(integer, Return(Literal(3))).body.children == (
        Return(Literal(3)),
    )


def test_cst_018_none_and_top_type_return_contract() -> None:
    none_type = ValueType(ValueKind.NONE)
    assert _definition(none_type, Return()).body.children == (Return(),)
    assert _definition(none_type, Return(NoneLiteral())).body.children == (
        Return(NoneLiteral()),
    )
    with pytest.raises(ConstructError, match="return type mismatch"):
        _definition(none_type, Return(Literal(1)))
    for kind in (ValueKind.ANY, ValueKind.OBJECT):
        assert _definition(ValueType(kind), Return(NoneLiteral()))
        assert _definition(ValueType(kind), Return(Literal(2)))
        with pytest.raises(ConstructError, match="return type mismatch"):
            _definition(ValueType(kind), Return())


def _branch(value: Return) -> Branch:
    return Branch(BooleanLiteral(True), Block((value,)), Block(()))


def _while(value: Return) -> While:
    return While(BooleanLiteral(True), Block((value,)), Block(()))


def _for(value: Return) -> For:
    symbol = Symbol("n", ValueType(ValueKind.INTEGER), "int")
    return For(
        IterationEntry(Reference(symbol), Range((Literal(2),))),
        Block((value,)),
        Block(()),
    )


def _with(value: Return) -> With:
    return With((ContextEntry(Literal(1)),), Block((value,)))


def _try_handler(value: Return) -> Try:
    return Try(Block(()), (ExceptHandler(("ValueError",), Block((value,))),))


def _try_finally(value: Return) -> Try:
    return Try(Block(()), finally_body=Block((value,)))


@pytest.mark.parametrize(
    "control",
    [_branch, _while, _for, _with, _try_handler, _try_finally],
)
def test_cst_017_nested_control_blocks_validate_returns(
    control: Callable[[Return], Construct],
) -> None:
    bad_return = Return(BooleanLiteral(True))
    with pytest.raises(ConstructError, match="return type mismatch"):
        _definition(ValueType(ValueKind.INTEGER), control(bad_return))
    assert _definition(ValueType(ValueKind.INTEGER), control(Return(Literal(5))))


def test_cst_019_nested_function_owns_its_return() -> None:
    inner = FunctionDefinition(
        _signature(ValueType(ValueKind.STRING), "inner"),
        Block((Return(Literal("ok")),)),
    )
    # No all-path inference: outer need not have a Return at all.
    outer = _definition(ValueType(ValueKind.INTEGER), inner)
    assert outer.body.children == (inner,)
    # But a Return directly owned by the outer function is checked.
    with pytest.raises(ConstructError, match="return type mismatch"):
        _definition(ValueType(ValueKind.INTEGER), inner, Return(Literal("bad")))


def test_cst_017_nominal_return_subtyping_but_not_unrelated_types() -> None:
    base = InstanceType("Base")
    derived = InstanceType("Derived", base=base)
    other = InstanceType("Other")
    expected = ValueType(ValueKind.INSTANCE, instance_type=base)
    for actual in (base, derived):
        symbol = Symbol(
            "instance", ValueType(ValueKind.INSTANCE, instance_type=actual), actual.name
        )
        assert _definition(expected, Return(Reference(symbol)))
    unrelated = Symbol(
        "unrelated", ValueType(ValueKind.INSTANCE, instance_type=other), other.name
    )
    with pytest.raises(ConstructError, match="return type mismatch"):
        _definition(expected, Return(Reference(unrelated)))


def test_frt_009_return_diagnostics_are_still_source_local() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython, match="Return type mismatch"):
        frontend.parse("def f() -> int:\n    if True:\n        return 'bad'\n")
    with pytest.raises(UnsupportedPython, match="Return value is required"):
        frontend.parse("def f() -> int:\n    return\n")
    with pytest.raises(UnsupportedPython, match="cannot return a value"):
        frontend.parse("def f() -> None:\n    return 1\n")
    model = frontend.parse("def f() -> int:\n    if True:\n        return 1\n")
    assert isinstance(model.body.children[0], FunctionDefinition)
