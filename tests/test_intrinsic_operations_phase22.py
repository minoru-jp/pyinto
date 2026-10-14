"""SDD phase 22: explicit, strictly typed intrinsic value operations.

This test set tests Model and Frontend contracts, not Python runtime or the
Target ABI. Existing Constructs and Realization are left unchanged.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Absolute,
    Arithmetic,
    Assign,
    BooleanLiteral,
    ConditionalExpression,
    ConstructError,
    DictValue,
    ExpressionStatement,
    Extremum,
    FunctionCall,
    FunctionDefinition,
    Initialize,
    Length,
    ListValue,
    Literal,
    Reference,
    Return,
    Symbol,
    TupleValue,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def _parse(source: str) -> object:
    return PythonFrontend().parse(source)


def _initialized(source: str) -> object:
    return _parse(source).body.children[-1].value  # type: ignore[attr-defined]


def _has_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (tuple, list)):
        return any(_has_ast(part) for part in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_has_ast(getattr(value, fld.name)) for fld in fields(value))
    return False


@pytest.mark.parametrize(
    "operand",
    [
        Literal("hi"),
        TupleValue((Literal(1), Literal("two"))),
        ListValue((Literal(1),), ValueType(ValueKind.INTEGER)),
        DictValue((), ValueType(ValueKind.STRING), ValueType(ValueKind.INTEGER)),
    ],
)
def test_cst_045_length_models_supported_collection_or_string(operand: object) -> None:
    expression = Length(operand)  # type: ignore[arg-type]
    assert expression.kind is ValueKind.INTEGER
    assert expression.value_type == ValueType(ValueKind.INTEGER)
    assert expression.parts() == {"operand": operand}
    assert expression.accepts_part_name("operand")
    assert not expression.accepts_part_name("result")
    with pytest.raises(FrozenInstanceError):
        expression.operand = Literal("different")  # type: ignore[misc]


@pytest.mark.parametrize(
    "value",
    [
        Literal(1),
        BooleanLiteral(True),
        Reference(Symbol("x", ValueType(ValueKind.OBJECT), "object")),
        None,
    ],
)
def test_cst_045_length_rejects_unadopted_value_kinds(value: object) -> None:
    with pytest.raises(ConstructError, match="typed str, tuple, list or dict"):
        Length(value)  # type: ignore[arg-type]


def test_cst_046_absolute_keeps_child_as_unexecuted_value() -> None:
    arg = Arithmetic(Literal(1), "-", Literal(10))
    node = Absolute(arg)
    assert node.parts() == {"operand": arg}
    assert node.kind is ValueKind.INTEGER
    assert node.value_type == ValueType(ValueKind.INTEGER)
    with pytest.raises(FrozenInstanceError):
        node.operand = Literal(1)  # type: ignore[misc]


@pytest.mark.parametrize("bad", [Literal("x"), BooleanLiteral(True), None])
def test_cst_046_absolute_rejects_non_integer(bad: object) -> None:
    with pytest.raises(ConstructError, match="typed integer"):
        Absolute(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["min", "max"])
def test_cst_047_extremum_preserves_order_and_identity(operation: str) -> None:
    left = Reference(Symbol("left", ValueType(ValueKind.INTEGER), "int"))
    middle = Literal(-1)
    right = Arithmetic(Literal(3), "+", Literal(4))
    node = Extremum(operation, (left, middle, right))
    assert node.kind is ValueKind.INTEGER
    assert node.parts() == {
        "operation": operation,
        "operands": (left, middle, right),
    }
    assert node.value_type == ValueType(ValueKind.INTEGER)
    with pytest.raises(FrozenInstanceError):
        node.operation = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "operation, items, message",
    [
        ("median", (Literal(1), Literal(2)), "operation must be min or max"),
        ("min", (Literal(1),), "at least two typed integers"),
        ("max", (), "at least two typed integers"),
        ("min", (Literal(1), Literal("text")), "at least two typed integers"),
        ("max", (BooleanLiteral(True), Literal(0)), "at least two typed integers"),
    ],
)
def test_cst_047_invalid_extremum_fails_before_realization(
    operation: str, items: tuple[object, ...], message: str
) -> None:
    with pytest.raises(ConstructError, match=message):
        Extremum(operation, items)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "source, expected_inner",
    [
        ("s: str = 'é猫'\nn: int = len(s)", Reference),
        ("xs: list[int] = [1, 2]\nn: int = len(xs)", Reference),
        ("mapping: dict[str, int] = {'x': 1}\nn: int = len(mapping)", Reference),
        ("t: tuple[int, str] = (1, 'x')\nn: int = len(t)", Reference),
        ("n: int = len((1, 'x'))", TupleValue),
        ("n: int = len([1, 2])", ListValue),
        ("n: int = len({'x': 1})", DictValue),
        ("n: int = len('ab')", Literal),
    ],
)
def test_frt_039_len_recognizes_typed_values(
    source: str, expected_inner: type[object]
) -> None:
    expression = _initialized(source)
    assert isinstance(expression, Length)
    assert isinstance(expression.operand, expected_inner)
    assert not _has_ast(expression)


def test_frt_039_dynamic_length_of_mutable_reference_is_not_folded() -> None:
    program = _parse(
        "xs: list[int] = [1]\nother: list[int] = xs\nother[1] = 2\nn: int = len(xs)\n"
    )
    expression = program.body.children[-1].value  # type: ignore[attr-defined]
    assert isinstance(expression, Length)
    assert isinstance(expression.operand, Reference)
    assert expression.operand.symbol.name == "xs"


def test_frt_039_len_keeps_nested_unevaluated_expression() -> None:
    node = _initialized(
        "def generate() -> list[int]:\n    return [1, 2]\nn: int = len(generate())\n"
    )
    assert isinstance(node, Length)
    assert isinstance(node.operand, FunctionCall)
    assert node.operand.signature.name == "generate"


@pytest.mark.parametrize(
    "source, intrinsic_type",
    [
        ("n: int = abs(-4)", Absolute),
        ("n: int = abs(1 - 5)", Absolute),
        ("n: int = min(8, 2)", Extremum),
        ("n: int = max(1, 9, -3)", Extremum),
        ("n: int = max(1, min(4, 2))", Extremum),
        ("n: int = abs(min(1, -3))", Absolute),
        ("n: int = min(len('a'), abs(-4))", Extremum),
    ],
)
def test_frt_040_integer_intrinsics_are_normalized(
    source: str, intrinsic_type: type[object]
) -> None:
    expression = _initialized(source)
    assert isinstance(expression, intrinsic_type)
    assert not _has_ast(expression)


def test_frt_040_extremum_operand_order_and_typed_result() -> None:
    expression = _initialized(
        "def counter(n: int) -> int:\n"
        "    return n\n"
        "n: int = min(counter(1), counter(2), counter(3))\n"
    )
    assert isinstance(expression, Extremum)
    assert expression.operation == "min"
    assert [arg.arguments[0].value for arg in expression.operands] == [1, 2, 3]  # type: ignore[union-attr]


def test_frt_040_with_function_return_and_conditional_expression() -> None:
    program = _parse(
        "def measure(values: list[int]) -> int:\n"
        "    return abs(len(values) - 3)\n"
        "xs: list[int] = [1, 2]\n"
        "n: int = measure(xs) if True else max(10, 20)\n"
    )
    func = program.body.children[0]  # type: ignore[attr-defined]
    assert isinstance(func, FunctionDefinition)
    ret = func.body.children[0]
    assert isinstance(ret, Return)
    assert isinstance(ret.value, Absolute)
    assert isinstance(ret.value.operand, Arithmetic)
    assert isinstance(ret.value.operand.left, Length)
    final = program.body.children[-1].value  # type: ignore[attr-defined]
    assert isinstance(final, ConditionalExpression)
    assert isinstance(final.when_false, Extremum)


def test_frt_040_intrinsic_expression_statements_stay_structural() -> None:
    program = _parse("xs: list[int] = [1]\nlen(xs)\nabs(-1)\nmax(1, 3)\n")
    statements = program.body.children[1:]  # type: ignore[attr-defined]
    assert all(isinstance(node, ExpressionStatement) for node in statements)
    assert [type(node.value) for node in statements] == [Length, Absolute, Extremum]


@pytest.mark.parametrize(
    "source, diagnostic",
    [
        ("n: int = len(1)", "Length requires"),
        ("n: int = len(True)", "Length requires"),
        ("n: int = len(None)", "Length requires"),
        ("x: object = 'abc'\nn: int = len(x)", "Length requires"),
        ("n: int = len()", "exactly one argument"),
        ("n: int = len('a', 'b')", "exactly one argument"),
        ("n: int = len(obj='a')", "positional arguments only"),
        ("n: int = len(*('a',))", "positional arguments only"),
        ("n: int = abs('x')", "Absolute requires"),
        ("n: int = abs(True)", "Absolute requires"),
        ("n: int = abs()", "exactly one argument"),
        ("n: int = min(1)", "at least two scalar arguments"),
        ("n: int = min([1, 2])", "at least two scalar arguments"),
        ("n: int = max(1, True)", "at least two typed integers"),
        ("n: int = max('a', 'z')", "at least two typed integers"),
        ("n: int = max(1, 2, key=abs)", "positional arguments only"),
        ("n: int = min(*(1, 2))", "positional arguments only"),
        ("n: int = zip([1, 2])", "Unregistered interface mapping call"),
    ],
)
def test_frt_041_rejects_unadopted_intrinsic_semantics(
    source: str, diagnostic: str
) -> None:
    with pytest.raises(UnsupportedPython, match=diagnostic):
        _parse(source)


def test_frt_041_user_defined_function_named_len_is_not_intercepted() -> None:
    program = _parse("def len(n: int) -> int:\n    return n\nvalue: int = len(3)\n")
    expression = program.body.children[-1].value  # type: ignore[attr-defined]
    assert isinstance(expression, FunctionCall)
    assert expression.signature.name == "len"


def test_frt_041_typed_callable_variable_named_abs_is_not_intercepted() -> None:
    program = _parse(
        "from typing import Callable\n"
        "def id(n: int) -> int:\n"
        "    return n\n"
        "abs: Callable[[int], int] = id\n"
        "result: int = abs(10)\n"
    )
    from pyinto.constructs import FunctionValueCall

    assert isinstance(program.body.children[-1].value, FunctionValueCall)  # type: ignore[attr-defined]


def test_frt_041_shadowed_noncallable_builtin_must_not_normalize() -> None:
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        _parse("len: int = 3\nn: int = len(4)")


@pytest.mark.parametrize("node_name", ["Length", "Absolute", "Extremum"])
def test_cst_045_047_unregistered_target_realization_rejects(node_name: str) -> None:
    value = {
        "Length": Length(Literal("x")),
        "Absolute": Absolute(Literal(1)),
        "Extremum": Extremum("min", (Literal(1), Literal(2))),
    }[node_name]
    before = value.parts().copy()
    with pytest.raises(ConstructError, match=f"No 'c' realization for {node_name}"):
        realize(value, realizations=c_bindings())
    assert value.parts() == before


def test_cst_045_047_existing_constructs_remain_unchanged() -> None:
    source = "n: int = abs(-3)\nn = min(4, max(1, 2))\n"
    result = _parse(source)
    assert isinstance(result.body.children[0], Initialize)  # type: ignore[attr-defined]
    assert isinstance(result.body.children[1], Assign)  # type: ignore[attr-defined]
    assert isinstance(result.body.children[1].value, Extremum)  # type: ignore[attr-defined]
