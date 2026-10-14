"""SDD 24: explicit string and floating arithmetic, no Target Realization."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    Arithmetic,
    ConstructError,
    FloatingArithmetic,
    FloatingComparison,
    FloatingLiteral,
    FloatingUnary,
    Literal,
    StringComparison,
    StringConcat,
    StringContains,
    StringElement,
    StringRepeat,
    ValueKind,
    ValueType,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def value(source: str) -> object:
    result = PythonFrontend().parse(source)
    return result.body.children[-1].value  # type: ignore[attr-defined]


def test_cst_050_float_literal_is_distinct_from_int_and_immutable() -> None:
    result = FloatingLiteral(1.25)
    assert result.kind is ValueKind.FLOAT
    assert result.value_type == ValueType(ValueKind.FLOAT)
    assert ValueType(ValueKind.FLOAT).annotation() == "float"
    with pytest.raises(FrozenInstanceError):
        result.value = 3.0  # type: ignore[misc]
    with pytest.raises(ValueError, match="integer or string"):
        Literal(1.25)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad", [True, 1, "1.0", None, float("inf"), float("-inf"), float("nan")]
)
def test_cst_050_reject_untyped_or_nonfinite_floats(bad: object) -> None:
    with pytest.raises(ConstructError, match="finite float"):
        FloatingLiteral(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["+", "-", "*", "/"])
def test_cst_051_float_arithmetic_order_and_type(operation: str) -> None:
    left, right = FloatingLiteral(2.0), FloatingLiteral(3.0)
    op = FloatingArithmetic(left, operation, right)
    assert op.kind is ValueKind.FLOAT
    assert op.parts() == {"left": left, "op": operation, "right": right}
    assert isinstance(value(f"x: float = 2.0 {operation} 3.0"), FloatingArithmetic)
    with pytest.raises(ConstructError, match="float operands"):
        FloatingArithmetic(left, operation, Literal(2))


@pytest.mark.parametrize("operation", ["+", "-"])
def test_cst_051_float_unary_keeps_expression(operation: str) -> None:
    op = FloatingUnary(operation, FloatingLiteral(4.0))
    assert op.kind is ValueKind.FLOAT
    assert op.parts()["operand"] == FloatingLiteral(4.0)
    parsed = value(f"x: float = {operation}4.0")
    assert isinstance(parsed, FloatingUnary)
    with pytest.raises(ConstructError, match="float operand"):
        FloatingUnary(operation, Literal(2))


@pytest.mark.parametrize("operator", ["<", "<=", ">", ">=", "==", "!="])
def test_cst_052_float_comparison(operator: str) -> None:
    parsed = value(f"b: bool = 1.0 {operator} 2.0")
    assert isinstance(parsed, FloatingComparison)
    assert parsed.kind is ValueKind.BOOLEAN
    assert parsed.parts()["op"] == operator


@pytest.mark.parametrize("operator", ["+", "-"])
def test_cst_053_string_concat_and_repeat_keeps_operands(operator: str) -> None:
    if operator == "+":
        parsed = value('s: str = "a" + "b"')
        assert isinstance(parsed, StringConcat)
        assert parsed.parts() == {"left": Literal("a"), "right": Literal("b")}
    else:
        parsed = value('s: str = "a" * 3')
        assert isinstance(parsed, StringRepeat)
        assert parsed.parts() == {"left": Literal("a"), "right": Literal(3)}
        assert isinstance(value('s: str = 3 * "a"'), StringRepeat)
    assert parsed.kind is ValueKind.STRING


@pytest.mark.parametrize("operator", ["<", "<=", ">", ">=", "==", "!="])
def test_cst_054_string_comparison(operator: str) -> None:
    parsed = value(f'b: bool = "a" {operator} "b"')
    assert isinstance(parsed, StringComparison)
    assert parsed.kind is ValueKind.BOOLEAN


def test_cst_054_string_membership_both_variants() -> None:
    assert isinstance(value('b: bool = "a" in "cat"'), StringContains)
    parsed = value('b: bool = "a" not in "cat"')
    assert isinstance(parsed, StringContains)
    assert parsed.variant() == "not_in"
    assert parsed.parts() == {"needle": Literal("a"), "haystack": Literal("cat")}


def test_cst_055_string_indexing_retains_index_without_evaluating() -> None:
    parsed = value('s: str = "日本語"[-1]')
    assert isinstance(parsed, StringElement)
    assert parsed.kind is ValueKind.STRING
    assert parsed.parts()["source"] == Literal("日本語")
    assert parsed.index == Literal(-1)
    parsed = value('s: str = "abc"[1 + 1]')
    assert isinstance(parsed, StringElement)
    assert isinstance(parsed.index, Arithmetic)


def test_frt_045_float_propagates_through_scopes_and_collections() -> None:
    source = """
def compute(x: float, y: float) -> float:
    return x * y + 1.25

x: float = compute(2.0, 3.0)
ys: list[float] = [1.0, x]
s: float = ys[0] / x
b: bool = x > 0.5
"""
    result = PythonFrontend().parse(source)
    assert len(result.body.children) == 5
    last_arithmetic = result.body.children[-2].value  # type: ignore[attr-defined]
    assert isinstance(last_arithmetic, FloatingArithmetic)
    last_comparison = result.body.children[-1].value  # type: ignore[attr-defined]
    assert isinstance(last_comparison, FloatingComparison)


def test_frt_046_string_composition_with_functions_and_conditional() -> None:
    source = """
def label(prefix: str, item: str) -> str:
    return prefix + item

text: str = label("id:", "one")
nonempty: bool = "id" in text
selection: str = text if nonempty else "missing"
indexed: str = selection[-1]
"""
    result = PythonFrontend().parse(source)
    last = result.body.children[-1].value  # type: ignore[attr-defined]
    assert isinstance(last, StringElement)
    contains = result.body.children[-3].value  # type: ignore[attr-defined]
    assert isinstance(contains, StringContains)


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        ("x: float = 1", "Annotated type"),
        ("x: int = 1.0", "Annotated type"),
        ("x: float = True", "Annotated type"),
        ("x: float = 1.0 + 2", "Unsupported operand"),
        ("x: float = 1.0 // 2.0", "Unsupported floating arithmetic"),
        ("x: float = 1.0 ** 2.0", "Unsupported arithmetic operator"),
        ("x: float = 1e309", "finite float"),
        ("b: bool = 1.0 == 2", "Comparison requires matching"),
        ("b: bool = 'a' == 2", "Comparison requires matching"),
        ("b: bool = 2 in 'foo'", "String membership requires"),
        ("s: str = 'a' - 'b'", "Unsupported operand"),
        ("s: str = 'a' * 1.5", "Unsupported operand"),
        ("s: str = 'abc'[1.0]", "String indexing requires"),
        ("s: str = 'abc'[0:True]", "Slice stop requires an integer"),
        ("s: str = str([3])", "type mismatch"),
    ],
)
def test_frt_047_refuses_unadopted_semantics(source: str, diagnostic: str) -> None:
    with pytest.raises(UnsupportedPython, match=diagnostic):
        PythonFrontend().parse(source)


def test_cst_053_manual_nodes_reject_invalid_shapes() -> None:
    with pytest.raises(ConstructError):
        StringConcat(Literal("a"), Literal(3))
    with pytest.raises(ConstructError):
        StringRepeat(Literal("a"), Literal("b"))
    with pytest.raises(ConstructError):
        StringComparison(Literal("a"), "in", Literal("b"))
    with pytest.raises(ConstructError):
        StringContains(Literal("a"), Literal(1))
    with pytest.raises(ConstructError):
        StringElement(Literal("a"), FloatingLiteral(1.0))
    with pytest.raises(ConstructError):
        FloatingComparison(Literal(2), "==", FloatingLiteral(2.0))
