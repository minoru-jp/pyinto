"""SDD phase 7: typed arithmetic and Boolean expressions in the Model only."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Arithmetic,
    Assign,
    BooleanNot,
    BooleanOperation,
    Branch,
    Comparison,
    ConstructError,
    Initialize,
    IntegerUnary,
    Literal,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def _integer(name: str = "n") -> Reference:
    return Reference(Symbol(name, ValueType(ValueKind.INTEGER), "int"))


def _boolean(name: str = "flag") -> Reference:
    return Reference(Symbol(name, ValueType(ValueKind.BOOLEAN), "bool"))


def _contains_ast(obj: object) -> bool:
    if isinstance(obj, ast.AST):
        return True
    if isinstance(obj, (list, tuple)):
        return any(_contains_ast(value) for value in obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return any(_contains_ast(getattr(obj, fld.name)) for fld in fields(obj))
    return False


@pytest.mark.parametrize("operator", ["+", "-", "*", "//", "%"])
def test_cst_015_arithmetic_keeps_operator_and_children(operator: str) -> None:
    left, right = _integer(), Literal(2)
    expression = Arithmetic(left, operator, right)
    assert expression.kind is ValueKind.INTEGER
    assert expression.parts() == {"left": left, "op": operator, "right": right}
    assert expression.HOLES == frozenset({"left", "op", "right"})


@pytest.mark.parametrize("operator", ["+", "-"])
def test_cst_015_integer_unary_is_structural(operator: str) -> None:
    operand = _integer()
    expression = IntegerUnary(operator, operand)
    assert expression.kind is ValueKind.INTEGER
    assert expression.parts() == {"op": operator, "operand": operand}


@pytest.mark.parametrize(
    "factory, message",
    [
        (lambda: Arithmetic(Literal(1), "/", Literal(2)), "Unsupported arithmetic"),
        (lambda: Arithmetic(Literal("a"), "+", Literal(2)), "requires integer"),
        (lambda: Arithmetic(_boolean(), "-", Literal(1)), "requires integer"),
        (lambda: IntegerUnary("!", _integer()), "Unsupported integer unary"),
        (lambda: IntegerUnary("-", Literal("a")), "requires an integer"),
        (
            lambda: BooleanOperation("xor", (_boolean(), _boolean())),
            "Unsupported Boolean",
        ),
        (lambda: BooleanOperation("and", (_boolean(),)), "at least two"),
        (lambda: BooleanOperation("or", (_boolean(), Literal(1))), "requires Boolean"),
        (lambda: BooleanNot(_integer()), "requires a Boolean"),
    ],
)
def test_cst_015_016_invalid_construct_fails_immediately(
    factory: object, message: str
) -> None:
    assert callable(factory)
    with pytest.raises(ConstructError, match=message):
        factory()  # type: ignore[operator]


def test_cst_016_boolean_structure_preserves_order_and_nesting() -> None:
    a, b, c = _boolean("a"), _boolean("b"), _boolean("c")
    nested = BooleanOperation("or", (b, c))
    expression = BooleanOperation("and", (a, BooleanNot(nested)))
    assert expression.kind is ValueKind.BOOLEAN
    assert expression.parts()["values"] == (a, BooleanNot(nested))
    assert nested.parts()["values"] == (b, c)
    assert isinstance(expression.parts()["values"][1], BooleanNot)


def test_frt_007_arithmetic_tree_and_existing_negative_literal() -> None:
    program = PythonFrontend().parse(
        "n: int = -3\nm: int = (n + 2) * (9 // 4)\nm = m % 5\nm = -m"
    )
    initial, second, third, fourth = program.body.children
    assert isinstance(initial, Initialize)
    assert initial.value == Literal(-3)
    assert isinstance(second, Initialize)
    assert isinstance(second.value, Arithmetic)
    assert second.value.operator == "*"
    assert isinstance(second.value.left, Arithmetic)
    assert second.value.left.operator == "+"
    assert isinstance(second.value.right, Arithmetic)
    assert second.value.right.operator == "//"
    assert isinstance(third, Assign)
    assert isinstance(third.value, Arithmetic)
    assert third.value.operator == "%"
    assert isinstance(fourth, Assign)
    assert isinstance(fourth.value, IntegerUnary)
    assert fourth.value.parts()["operand"] == _integer("m")
    assert not _contains_ast(program)


def test_frt_008_boolean_tree_can_be_condition_of_if_and_while() -> None:
    program = PythonFrontend().parse(
        "n: int = 0\n"
        "if not (n < 3 or n == 7) and n != 9:\n    n = n + 1\n"
        "while n < 5 and not (n == 3):\n    n = n + 1"
    )
    _, branch, loop = program.body.children
    assert isinstance(branch, Branch)
    assert isinstance(branch.condition, BooleanOperation)
    assert branch.condition.operator == "and"
    first, last = branch.condition.operands
    assert isinstance(first, BooleanNot)
    assert isinstance(first.operand, BooleanOperation)
    assert first.operand.operator == "or"
    assert isinstance(last, Comparison)
    assert isinstance(loop.condition, BooleanOperation)
    assert loop.condition.operator == "and"
    assert isinstance(loop.condition.operands[1], BooleanNot)
    assert not _contains_ast(program)


def test_frt_007_does_not_evaluate_arithmetic_during_parsing() -> None:
    program = PythonFrontend().parse("n: int = 1 // 0\nn = -n")
    first = program.body.children[0]
    assert isinstance(first, Initialize)
    assert isinstance(first.value, Arithmetic)
    assert first.value.parts()["right"] == Literal(0)


@pytest.mark.parametrize(
    "source, fragment",
    [
        ("n: int = 1 / 2", "Annotated type does not match initializer"),
        ("n: int = 2 ** 4", "Unsupported arithmetic operator"),
        ("n: int = 'a' + 'b'", "Annotated type does not match initializer"),
        ("n: int = 1 + '2'", "Unsupported operand types for arithmetic"),
        ("n: int = 1\nn = not n", "Boolean not requires a Boolean operand"),
        (
            "n: int = 1\nif n and n:\n    n = 1",
            "Boolean operation requires Boolean operands",
        ),
        ("n = 1 + 2", "explicit type annotation"),
    ],
)
def test_frt_007_008_unsupported_syntax_fails_explicitly(
    source: str, fragment: str
) -> None:
    with pytest.raises(UnsupportedPython, match=fragment) as exc:
        PythonFrontend().parse(source)
    assert "line " in str(exc.value)


def test_expression_model_is_independent_of_target_realization() -> None:
    model = PythonFrontend().parse("n: int = 1 + 2")
    snapshot = repr(model)
    with pytest.raises(ConstructError, match="No 'c' realization for Arithmetic"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot
    assert not _contains_ast(model)
    assert PythonFrontend().parse("n: int = 1 + 2") == model
