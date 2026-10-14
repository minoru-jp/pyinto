"""SDD 23: typed intrinsic collection aggregations, without Target execution."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Arithmetic,
    BooleanAggregate,
    BooleanLiteral,
    ConditionalExpression,
    ConstructError,
    ExpressionStatement,
    FunctionCall,
    FunctionDefinition,
    FunctionValueCall,
    Initialize,
    IntegerSum,
    ListValue,
    Literal,
    Range,
    Reference,
    Return,
    TupleValue,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def parse(source: str) -> object:
    return PythonFrontend().parse(source)


def last_value(source: str) -> object:
    return parse(source).body.children[-1].value  # type: ignore[attr-defined]


def contains_ast(obj: object) -> bool:
    if isinstance(obj, ast.AST):
        return True
    if isinstance(obj, (list, tuple)):
        return any(contains_ast(item) for item in obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return any(contains_ast(getattr(obj, f.name)) for f in fields(obj))
    return False


@pytest.mark.parametrize(
    "source",
    [
        ListValue((Literal(3), Literal(-1)), ValueType(ValueKind.INTEGER)),
        TupleValue((Literal(2), Literal(-5))),
        TupleValue(()),
        Range((Literal(3),)),
    ],
)
def test_cst_048_integer_sum_accepts_only_known_integer_sequences(
    source: object,
) -> None:
    node = IntegerSum(source)  # type: ignore[arg-type]
    assert node.value_type == ValueType(ValueKind.INTEGER)
    assert node.parts() == {"iterable": source}
    assert node.accepts_part_name("iterable")
    assert node.accepts_part_name("start")
    with pytest.raises(FrozenInstanceError):
        node.iterable = Literal(1)  # type: ignore[misc]


def test_cst_048_start_retained_in_order_and_not_folded() -> None:
    source = ListValue((Literal(1), Literal(2)), ValueType(ValueKind.INTEGER))
    start = Arithmetic(Literal(4), "+", Literal(5))
    node = IntegerSum(source, start)
    assert node.parts() == {"iterable": source, "start": start}
    assert node.start is start
    assert node.kind is ValueKind.INTEGER


@pytest.mark.parametrize(
    "source",
    [
        Literal(1),
        Literal("123"),
        BooleanLiteral(True),
        ListValue((BooleanLiteral(True),), ValueType(ValueKind.BOOLEAN)),
        ListValue((Literal("hi"),), ValueType(ValueKind.STRING)),
        TupleValue((Literal(1), Literal("x"))),
        TupleValue((BooleanLiteral(True),)),
        None,
    ],
)
def test_cst_048_integer_sum_rejects_bad_source(source: object) -> None:
    with pytest.raises(ConstructError, match="IntegerSum requires"):
        IntegerSum(source)  # type: ignore[arg-type]


@pytest.mark.parametrize("start", [Literal("a"), BooleanLiteral(True), object()])
def test_cst_048_integer_sum_rejects_bad_start(start: object) -> None:
    with pytest.raises(ConstructError, match="IntegerSum start requires"):
        IntegerSum(TupleValue((Literal(1),)), start)  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["any", "all"])
@pytest.mark.parametrize(
    "source",
    [
        ListValue(
            (BooleanLiteral(True), BooleanLiteral(False)), ValueType(ValueKind.BOOLEAN)
        ),
        TupleValue((BooleanLiteral(True),)),
        TupleValue(()),
    ],
)
def test_cst_049_boolean_aggregation_is_typed_and_immutable(
    operation: str, source: object
) -> None:
    node = BooleanAggregate(operation, source)  # type: ignore[arg-type]
    assert node.kind is ValueKind.BOOLEAN
    assert node.value_type == ValueType(ValueKind.BOOLEAN)
    assert node.parts() == {"operation": operation, "iterable": source}
    with pytest.raises(FrozenInstanceError):
        node.operation = "different"  # type: ignore[misc]


@pytest.mark.parametrize(
    "operation, source, expected",
    [
        ("every", TupleValue((BooleanLiteral(True),)), "operation must"),
        ("any", ListValue((Literal(1),), ValueType(ValueKind.INTEGER)), "requires"),
        ("all", TupleValue((Literal(1),)), "requires"),
        ("any", Literal(1), "requires"),
        ("any", None, "requires"),
    ],
)
def test_cst_049_boolean_aggregation_rejects_wrong_shape(
    operation: str, source: object, expected: str
) -> None:
    with pytest.raises(ConstructError, match=expected):
        BooleanAggregate(operation, source)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "source, expected_type",
    [
        ("n: int = sum([1, 2, 3])", ListValue),
        ("n: int = sum((1, 2, 3))", TupleValue),
        ("n: int = sum(())", TupleValue),
        ("n: int = sum(range(2, 9))", Range),
        ("items: list[int] = []\nn: int = sum(items)", Reference),
        ("items: list[int] = [1, 2]\nn: int = sum(items, 10)", Reference),
    ],
)
def test_frt_042_integer_sum_normalization(
    source: str, expected_type: type[object]
) -> None:
    value = last_value(source)
    assert isinstance(value, IntegerSum)
    assert isinstance(value.iterable, expected_type)
    assert not contains_ast(value)


def test_frt_042_sum_start_preserves_expression_and_order() -> None:
    node = last_value(
        "def numbers() -> list[int]:\n"
        "    return [1, 3]\n"
        "def first() -> int:\n"
        "    return 10\n"
        "result: int = sum(numbers(), first())\n"
    )
    assert isinstance(node, IntegerSum)
    assert isinstance(node.iterable, FunctionCall)
    assert node.iterable.signature.name == "numbers"
    assert isinstance(node.start, FunctionCall)
    assert node.start.signature.name == "first"
    assert list(node.parts()) == ["iterable", "start"]


def test_frt_042_sum_works_inside_function_and_conditional() -> None:
    result = parse(
        "def total(xs: list[int], flag: bool) -> int:\n"
        "    return sum(xs) if flag else sum((1, 2), 5)\n"
    )
    function = result.body.children[0]  # type: ignore[attr-defined]
    assert isinstance(function, FunctionDefinition)
    statement = function.body.children[0]
    assert isinstance(statement, Return)
    assert isinstance(statement.value, ConditionalExpression)
    assert isinstance(statement.value.when_true, IntegerSum)
    assert isinstance(statement.value.when_false, IntegerSum)


@pytest.mark.parametrize(
    "source, expected_op, expected_type",
    [
        ("result: bool = any([True, False])", "any", ListValue),
        ("result: bool = all((True, False))", "all", TupleValue),
        ("result: bool = any(())", "any", TupleValue),
        ("result: bool = all(())", "all", TupleValue),
        ("items: list[bool] = []\nresult: bool = all(items)", "all", Reference),
    ],
)
def test_frt_043_boolean_aggregations_are_structural(
    source: str, expected_op: str, expected_type: type[object]
) -> None:
    node = last_value(source)
    assert isinstance(node, BooleanAggregate)
    assert node.operation == expected_op
    assert isinstance(node.iterable, expected_type)
    assert not contains_ast(node)


def test_frt_043_nested_boolean_aggregation_and_condition() -> None:
    node = last_value("result: bool = any([all((True, False)), True])")
    assert isinstance(node, BooleanAggregate)
    assert isinstance(node.iterable, ListValue)
    assert isinstance(node.iterable.items[0], BooleanAggregate)


def test_frt_043_expression_statement_keeps_structural_value() -> None:
    program = parse("xs: list[int] = [1]\nsum(xs)\nany((True, False))\n")
    assert isinstance(program.body.children[0], Initialize)  # type: ignore[attr-defined]
    assert isinstance(program.body.children[1], ExpressionStatement)  # type: ignore[attr-defined]
    assert isinstance(program.body.children[1].value, IntegerSum)  # type: ignore[attr-defined]
    assert isinstance(program.body.children[2].value, BooleanAggregate)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "source, message",
    [
        ("n: int = sum()", "one iterable"),
        ("n: int = sum([1], 0, 0)", "one iterable"),
        ("n: int = sum([1], start=0)", "positional arguments only"),
        ("n: int = sum(*([1],))", "positional arguments only"),
        ("n: int = sum([])", "Empty list needs an explicit list type"),
        ("n: int = sum([True])", "IntegerSum requires"),
        ("n: int = sum((1, 'a'))", "IntegerSum requires"),
        ("n: int = sum('abc')", "IntegerSum requires"),
        ("n: int = sum([1], True)", "IntegerSum start requires"),
        ("result: bool = any()", "exactly one iterable"),
        ("result: bool = all(True)", "requires list"),
        ("result: bool = any([1])", "requires list"),
        ("result: bool = all((True, 1))", "requires list"),
        ("result: bool = any(range(3))", "requires list"),
        ("result: bool = any([True], extra=True)", "positional arguments only"),
        ("result: bool = all(*((True,),))", "positional arguments only"),
    ],
)
def test_frt_044_strict_rejection(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        parse(source)


def test_frt_044_shadowed_builtin_is_resolved_as_user_function() -> None:
    result = last_value("def sum(n: int) -> int:\n    return n\nx: int = sum(7)\n")
    assert isinstance(result, FunctionCall)
    assert result.signature.name == "sum"


def test_frt_044_shadowed_callable_is_indirect_call_not_aggregation() -> None:
    result = last_value(
        "from typing import Callable\n"
        "def identity(n: int) -> int:\n"
        "    return n\n"
        "all: Callable[[int], int] = identity\n"
        "result: int = all(1)\n"
    )
    assert isinstance(result, FunctionValueCall)


def test_frt_044_unknown_intrinsic_and_shadowed_noncallable_reject() -> None:
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        parse("enumerate([1, 2])")
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        parse("sum: int = 1\nresult: int = sum([1, 2])")


@pytest.mark.parametrize(
    "node",
    [
        IntegerSum(TupleValue((Literal(1), Literal(2)))),
        BooleanAggregate("any", TupleValue((BooleanLiteral(True),))),
        BooleanAggregate("all", TupleValue(())),
    ],
)
def test_cst_048_049_unregistered_c_realization_fails_without_model_mutation(
    node: object,
) -> None:
    before = node.parts().copy()  # type: ignore[attr-defined]
    with pytest.raises(ConstructError, match="No 'c' realization"):
        realize(node, realizations=c_bindings())  # type: ignore[arg-type]
    assert node.parts() == before  # type: ignore[attr-defined]
