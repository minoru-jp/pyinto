"""Iteration 46: typed *args in self-defined functions, without Target ABI guesses."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    AugAssign,
    ConstructError,
    For,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    Initialize,
    IntegerSum,
    Length,
    Literal,
    Parameter,
    ParameterRole,
    Reference,
    Return,
    Symbol,
    TupleType,
    TupleValue,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython


def parse(source: str):
    return PythonFrontend().parse(source).body.children


def test_variadic_signature_body_binding_and_zero_three_calls() -> None:
    func, empty, triple = parse(
        "def count(*values: int) -> int:\n"
        "    return len(values)\n"
        "empty: int = count()\n"
        "triple: int = count(1, 2, 3)\n"
    )
    assert isinstance(func, FunctionDefinition)
    assert func.signature.parameters == ()
    binding = func.signature.variadic_parameter
    assert binding is not None
    assert binding.role is ParameterRole.VARIADIC
    assert binding.scope == ("count",)
    assert binding.type == ValueType(
        ValueKind.TUPLE,
        tuple_type=TupleType(variadic_element_type=ValueType(ValueKind.INTEGER)),
    )
    assert binding.annotation == "tuple[int, ...]"
    slot = func.parts()["variadic_parameter"]
    assert isinstance(slot, Parameter)
    assert slot.symbol is binding
    assert isinstance(func.body.children[0], Return)
    result = func.body.children[0].value
    assert isinstance(result, Length)
    assert isinstance(result.operand, Reference)
    assert result.operand.symbol is binding
    assert isinstance(empty, Initialize) and isinstance(empty.value, FunctionCall)
    assert isinstance(triple, Initialize) and isinstance(triple.value, FunctionCall)
    assert empty.value.arguments == ()
    assert triple.value.arguments == (Literal(1), Literal(2), Literal(3))
    assert empty.value.signature is func.signature
    assert triple.value.signature is func.signature
    assert "call.variadic.tuple_binding" in required_contracts(triple.value)
    assert "function.variadic.tuple_binding" in required_contracts(func)
    assert "call.arguments.left_to_right" in required_contracts(triple.value)


def test_fixed_and_variadic_args_preserve_both_semantic_roles() -> None:
    func, call = parse(
        "def total(first: int, *rest: int) -> int:\n"
        "    value: int = first\n"
        "    for item in rest:\n"
        "        value += item\n"
        "    return value\n"
        "result: int = total(1, 2, 3)\n"
    )
    assert isinstance(func, FunctionDefinition)
    assert len(func.signature.parameters) == 1
    assert func.signature.parameters[0].name == "first"
    assert func.signature.variadic_parameter is not None
    loop = func.body.children[1]
    assert isinstance(loop, For)
    assert loop.entry.iterable.symbol is func.signature.variadic_parameter
    assert loop.entry.target.kind is ValueKind.INTEGER
    assert isinstance(loop.body.children[0], AugAssign)
    assert isinstance(call.value, FunctionCall)
    assert call.value.arguments == (Literal(1), Literal(2), Literal(3))


def test_builtin_sum_and_bool_aggregates_accept_runtime_tuple_shapes() -> None:
    func, _ = parse(
        "def total(*items: int) -> int:\n    return sum(items)\nx: int = total()\n"
    )
    assert isinstance(func.body.children[0].value, IntegerSum)
    bool_func, _ = parse(
        "def all_ok(*items: bool) -> bool:\n"
        "    return all(items)\n"
        "ok: bool = all_ok(True, False)\n"
    )
    assert (
        bool_func.signature.variadic_parameter.value_type.tuple_type.variadic_element_type.kind
        is ValueKind.BOOLEAN
    )


def test_homogeneous_tuple_annotation_accepts_known_fixed_length_and_empty() -> None:
    declarations = parse("a: tuple[int, ...] = (1, 2, 3)\nb: tuple[int, ...] = ()\n")
    assert all(isinstance(item, Initialize) for item in declarations)
    assert isinstance(declarations[0].value, TupleValue)
    assert isinstance(declarations[1].value, TupleValue)
    assert (
        declarations[0].symbol.value_type.tuple_type.variadic_element_type.kind
        is ValueKind.INTEGER
    )


def test_model_rejects_ambiguous_or_invalid_tuple_shapes() -> None:
    integer = ValueType(ValueKind.INTEGER)
    with pytest.raises(ConstructError, match="cannot have fixed"):
        TupleType((integer,), variadic_element_type=integer)
    with pytest.raises(ConstructError, match="supported element"):
        TupleType(variadic_element_type=ValueType(ValueKind.NONE))
    assert TupleType(()).annotation() == "tuple[()]"
    assert TupleType(variadic_element_type=integer).annotation() == "tuple[int, ...]"
    assert TupleType((integer,)).annotation() == "tuple[int]"


def test_defaults_keyword_and_varargs_evaluation_order() -> None:
    func, a, b, c = parse(
        "def f(x: int = 3, *rest: int) -> int:\n"
        "    return x\n"
        "a: int = f()\n"
        "b: int = f(4, 5, 6)\n"
        "c: int = f(x=7)\n"
    )
    assert isinstance(func, FunctionDefinition)
    assert isinstance(a.value, FunctionCall)
    assert a.value.arguments == (Literal(3),)
    assert a.value.omitted_arguments == (0,)
    assert a.value.supplied_evaluation_arguments == ()
    assert b.value.arguments == (Literal(4), Literal(5), Literal(6))
    assert b.value.supplied_evaluation_arguments == b.value.arguments
    assert c.value.arguments == (Literal(7),)
    assert c.value.omitted_arguments == ()
    assert func.signature.defaults_by_parameter == (Literal(3),)


def test_mixed_keyword_fixed_args_bind_correctly() -> None:
    _, actual = parse(
        "def f(x: int, y: int, *rest: int) -> int:\n"
        "    return x + y\n"
        "result: int = f(y=2, x=1)\n"
    )
    call = actual.value
    assert call.arguments == (Literal(1), Literal(2))
    assert call.argument_evaluation_order == (1, 0)
    assert "call.arguments.reordered" in required_contracts(call)


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("def f(*items) -> int:\n    return 1", "needs an element annotation"),
        ("def f(*items: None) -> int:\n    return 1", "Unsupported variadic"),
        ("def f(*items: int) -> int:\n    return 1\nf('x')", "type mismatch"),
        (
            "def f(a: int, *items: int) -> int:\n    return 1\nf()",
            "argument count mismatch",
        ),
        (
            "def f(a: int, *items: int) -> int:\n    return 1\nf(1, items=2)",
            "Unknown keyword",
        ),
        (
            "def f(*items: int) -> int:\n    return 1\nf(*[1, 2])",
            "Expanded call arguments",
        ),
        (
            "def f(*items: int) -> int:\n    return 1\nf(**{})",
            "Expanded keyword arguments",
        ),
        ("def f(**kwargs: int) -> int:\n    return 1", "requires simple typed"),
        ("def f(*items: int, x: int) -> int:\n    return 1", "requires simple typed"),
        (
            "from typing import Callable\ndef f(*items: int) -> int:\n    return 1\ng: Callable[[], int] = f",
            "no supported value type",
        ),
        (
            "def f(*items: int) -> int:\n    return 1\ndef g(f: int) -> int:\n    return f",
            "Reserved function parameter",
        ),
        (
            "def f(*items: int) -> int:\n    return items[0]",
            "Fixed tuple element access",
        ),
        (
            "def f(*items: int) -> int:\n    items.append(1)\n    return 1",
            "Unregistered interface mapping object",
        ),
        (
            "def f(*items: int) -> int:\n    return 1\ndef f(x: int) -> int:\n    return 1",
            "Duplicate",
        ),
        (
            "def f(x: int, *x: int) -> int:\n    return 1",
            "Duplicate function parameter",
        ),
    ],
)
def test_fail_closed(source: str, error: str) -> None:
    with pytest.raises(UnsupportedPython, match=error):
        parse(source)


def test_variadic_direct_call_model_checks_without_frontend() -> None:
    it = ValueType(ValueKind.INTEGER)
    var_tuple = ValueType(
        ValueKind.TUPLE, tuple_type=TupleType(variadic_element_type=it)
    )
    var = Symbol(
        "items",
        var_tuple,
        var_tuple.annotation(),
        scope=("f",),
        role=ParameterRole.VARIADIC,
    )
    sig = FunctionSignature("f", (), "int", it, variadic_parameter=var)
    assert FunctionCall(sig, (Literal(3), Literal(5))).arguments == (
        Literal(3),
        Literal(5),
    )
    with pytest.raises(
        ConstructError, match="Variadic function argument type mismatch"
    ):
        FunctionCall(sig, (Literal("bad"),))
    with pytest.raises(ConstructError, match="cannot be omitted defaults"):
        FunctionCall(sig, (Literal(3),), omitted_arguments=(0,))
    with pytest.raises(ConstructError, match="function values are unsupported"):
        _ = sig.callable_type
    with pytest.raises(ConstructError, match="no supported value type"):
        _ = sig.value_symbol


def test_target_does_not_silently_realize_runtime_variadic_tuple() -> None:
    from pyinto import realize
    from tests.support.c_realizer import c_bindings

    model = PythonFrontend().parse(
        "def count(*items: int) -> int:\n    return len(items)\nx: int = count(2, 3)\n"
    )
    with pytest.raises(ConstructError):
        realize(model, realizations=c_bindings())


def test_variadic_tuple_is_passed_as_one_typed_value_to_fixed_parameter() -> None:
    vararg, other = parse(
        "def consume(values: tuple[int, ...]) -> int:\n"
        "    return len(values)\n"
        "def outer(*items: int) -> int:\n"
        "    return consume(items)\n"
    )
    assert isinstance(other, FunctionDefinition)
    assert isinstance(vararg, FunctionDefinition)
    assert isinstance(other.body.children[0], Return)
    nested_call = other.body.children[0].value
    assert isinstance(nested_call, FunctionCall)
    assert nested_call.signature is vararg.signature
    assert isinstance(nested_call.arguments[0], Reference)
    assert nested_call.arguments[0].symbol is other.signature.variadic_parameter


def test_homogeneous_tuple_rejects_heterogeneous_initializer() -> None:
    with pytest.raises(UnsupportedPython, match="Annotated type does not match"):
        parse("values: tuple[int, ...] = (1, 'x')")
