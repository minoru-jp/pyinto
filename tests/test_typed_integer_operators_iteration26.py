"""Iteration 26: typed bit operations and int true division, without Target inference."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto import realize
from pyinto.constructs import (
    Arithmetic,
    AugAssign,
    ConstructError,
    FloatingArithmetic,
    FloatingLiteral,
    Initialize,
    IntegerTrueDivision,
    IntegerUnary,
    Literal,
    ValueKind,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def _last_value(code: str):
    item = PythonFrontend().parse(code).body.children[-1]
    assert isinstance(item, Initialize)
    return item.value


@pytest.mark.parametrize(
    ("expression", "operator"),
    [
        ("7 & 3", "&"),
        ("7 | 3", "|"),
        ("7 ^ 3", "^"),
        ("7 << 3", "<<"),
        ("7 >> 3", ">>"),
        ("-7 >> 2", ">>"),
        ("7 << -2", "<<"),
        ("(1 << 130) & (3 << 129)", "&"),
    ],
)
def test_integer_bitwise_ops_are_unfolded_typed_values(
    expression: str, operator: str
) -> None:
    node = _last_value(f"result: int = {expression}")
    assert isinstance(node, Arithmetic)
    assert node.operator == operator
    assert node.kind is ValueKind.INTEGER
    assert node.parts()["left"] is node.left
    assert node.parts()["right"] is node.right
    assert "integer.bitwise.unbounded" in required_contracts(node)
    if operator in {"<<", ">>"}:
        assert "integer.shift.python_counts" in required_contracts(node)
    else:
        assert "integer.shift.python_counts" not in required_contracts(node)
    assert "evaluation.operands.left_to_right" in required_contracts(node)


def test_integer_bitwise_complement_is_explicit_and_not_constant_folded() -> None:
    literal = _last_value("result: int = ~0")
    named = _last_value("x: int = 9\nresult: int = ~x")
    for node in (literal, named):
        assert isinstance(node, IntegerUnary)
        assert node.operator == "~"
        assert node.kind is ValueKind.INTEGER
        assert "integer.bitwise.unbounded" in required_contracts(node)
    assert literal.operand == Literal(0)
    assert required_contracts(_last_value("x: int = 3\ny: int = -x")) == frozenset()


def test_integer_true_division_is_not_integer_arithmetic_or_float_float() -> None:
    node = _last_value("result: float = 7 / 2")
    assert isinstance(node, IntegerTrueDivision)
    assert not isinstance(node, (Arithmetic, FloatingArithmetic))
    assert node.kind is ValueKind.FLOAT
    assert node.left == Literal(7)
    assert node.right == Literal(2)
    assert tuple(node.parts()) == ("left", "right")
    assert required_contracts(node) == {
        "evaluation.operands.left_to_right",
        "integer.true_division.python_float",
    }
    assert isinstance(_last_value("result: float = 7.0 / 2.0"), FloatingArithmetic)
    assert isinstance(_last_value("result: int = 7 // 2"), Arithmetic)
    assert isinstance(_last_value("result: float = 7 / 0"), IntegerTrueDivision)
    big = _last_value("result: float = (10 << 1000) / 2")
    assert isinstance(big, IntegerTrueDivision)
    with pytest.raises(FrozenInstanceError):
        node.left = Literal(9)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 & 1.0", "Unsupported operand types"),
        ("2.0 << 1.0", "Unsupported floating arithmetic"),
        ("2.0 & 1", "Unsupported operand types"),
        ("2 / 2.0", "Unsupported operand types"),
        ("2.0 / 2", "Unsupported operand types"),
        ("2 << True", "Unsupported operand types"),
        ("True & 1", "Unsupported operand types"),
        ("~1.0", "Bitwise complement requires an integer"),
        ("~True", "Integer unary operation requires an integer"),
        ("7 ** 2", "Unsupported arithmetic operator"),
    ],
)
def test_untyped_or_unimplemented_operations_remain_rejected(
    expression: str, expected: str
) -> None:
    with pytest.raises(UnsupportedPython, match=expected):
        PythonFrontend().parse(f"result: int = {expression}")


@pytest.mark.parametrize("expression", ["9 / 2", "9 / 0", "9 / -2"])
def test_true_division_does_not_implicitly_narrow_to_int(expression: str) -> None:
    with pytest.raises(UnsupportedPython, match="Annotated type does not match"):
        PythonFrontend().parse(f"result: int = {expression}")


def test_model_direct_validation_and_source_side_effect_order() -> None:
    with pytest.raises(ConstructError, match="requires two integers"):
        IntegerTrueDivision(Literal(1), FloatingLiteral(2.0))
    with pytest.raises(ConstructError, match="requires integer operands"):
        Arithmetic(Literal(1), "&", FloatingLiteral(3.0))
    with pytest.raises(ConstructError, match="Unsupported arithmetic"):
        Arithmetic(Literal(1), "**", Literal(2))
    with pytest.raises(ConstructError, match="requires an integer"):
        IntegerUnary("~", FloatingLiteral(2.0))

    program = PythonFrontend().parse(
        "def first() -> int:\n"
        "    return 3\n"
        "def second() -> int:\n"
        "    return 2\n"
        "value: int = first() << second()\n"
        "fraction: float = first() / second()"
    )
    shift = program.body.children[-2].value
    division = program.body.children[-1].value
    assert isinstance(shift, Arithmetic)
    assert isinstance(division, IntegerTrueDivision)
    assert shift.left is not shift.right
    assert division.left is not division.right
    assert "evaluation.operands.left_to_right" in required_contracts(shift)
    assert "evaluation.operands.left_to_right" in required_contracts(division)


@pytest.mark.parametrize(
    ("source", "op"),
    [
        ("n: int = 3\nn &= 1", "&"),
        ("n: int = 3\nn |= 1", "|"),
        ("n: int = 3\nn ^= 1", "^"),
        ("n: int = 3\nn <<= 1", "<<"),
        ("n: int = 3\nn >>= -1", ">>"),
    ],
)
def test_bitwise_augmented_rebinding_uses_existing_lvalue_semantics(
    source: str, op: str
) -> None:
    node = PythonFrontend().parse(source).body.children[-1]
    assert isinstance(node, AugAssign)
    assert node.operator == op
    assert "integer.bitwise.unbounded" in required_contracts(node)
    assert "assignment.augmented.target_once" in required_contracts(node)
    assert ("integer.shift.python_counts" in required_contracts(node)) == (
        op in {"<<", ">>"}
    )


def test_realization_admission_rejects_unclaimed_semantics_before_mutation() -> None:
    bit = _last_value("x: int = 4 << 2")
    division = _last_value("x: float = 4 / 2")

    @realizes(Arithmetic)
    class UnsafeBit:
        template = "${left} << ${right}"
        supports = ("evaluation.operands.left_to_right",)

    @realizes(IntegerTrueDivision)
    class UnsafeDivision:
        template = "${left} / ${right}"
        supports = ("evaluation.operands.left_to_right",)

    for node, recipe, missing in (
        (bit, UnsafeBit, "integer.bitwise.unbounded"),
        (division, UnsafeDivision, "integer.true_division.python_float"),
    ):
        registry = RealizationRegistry("fake", (recipe,))
        context = EmitContext(registry)
        with pytest.raises(ConstructError, match=missing):
            registry.recipe(node, context)
        assert context.headers == set()
        for pack in (c_bindings(), python_bindings()):
            with pytest.raises(ConstructError):
                realize(node, realizations=pack)


def test_existing_scalar_arithmetic_stays_without_new_bitwise_semantics() -> None:
    simple = _last_value("x: int = 7 + 2")
    assert required_contracts(simple) == {"evaluation.operands.left_to_right"}
    unary = _last_value("x: int = -3")
    assert unary == Literal(-3)
