"""Iteration 31: bounded fixed-tuple unpack, without Target implementations."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    Literal,
    Reference,
    Symbol,
    TupleValue,
    UnpackAssign,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION, required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes


def _last(source: str) -> UnpackAssign:
    node = PythonFrontend().parse(source).body.children[-1]
    assert isinstance(node, UnpackAssign)
    return node


def test_tuple_variable_unpack_preserves_identity_and_shapes() -> None:
    node = _last("""
pair: tuple[int, str] = (3, "a")
x: int = 0
s: str = ""
x, s = pair
""")
    assert [target.symbol.name for target in node.targets] == ["x", "s"]
    assert isinstance(node.value, Reference)
    assert node.value.symbol.name == "pair"
    assert node.parts() == {"targets": node.targets, "value": node.value}
    assert node.value.tuple_type is not None
    assert node.value.tuple_type.element_types == (
        ValueType(ValueKind.INTEGER),
        ValueType(ValueKind.STRING),
    )
    with pytest.raises(FrozenInstanceError):
        node.value = TupleValue(())  # type: ignore[misc]


def test_exchange_is_one_node_not_sequential_assigns() -> None:
    node = _last("""
a: int = 1
b: int = 2
a, b = b, a
""")
    assert isinstance(node.value, TupleValue)
    assert [
        value.symbol.name for value in node.value.items if isinstance(value, Reference)
    ] == ["b", "a"]
    assert len(node.targets) == 2
    assert {type(node).__name__} == {"UnpackAssign"}


def test_duplicate_target_is_legal_and_update_order_is_contract() -> None:
    node = _last("""
a: int = 0
a, a = 1, 2
""")
    assert node.targets[0].symbol is node.targets[1].symbol
    assert required_contracts(node) == {
        "assignment.unpack.rhs_once_before_writes",
        "assignment.unpack.targets_left_to_right",
    }


def test_function_tuple_return_is_not_repeated() -> None:
    program = PythonFrontend().parse("""
def make_pair() -> tuple[int, int]:
    return 1, 2
x: int = 0
y: int = 0
x, y = make_pair()
""")
    assert isinstance(program.body.children[0], FunctionDefinition)
    node = program.body.children[-1]
    assert isinstance(node, UnpackAssign)
    assert isinstance(node.value, FunctionCall)
    assert node.value.signature.name == "make_pair"


def test_tuple_unpack_with_zero_length_is_statically_defined() -> None:
    node = _last("""
nothing: tuple[()] = ()
() = nothing
""")
    assert node.targets == ()
    assert len(node.value.tuple_type.element_types) == 0  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("x: int = 0\nx, y = (1, 2)", "declared targets"),
        ("x: int = 0\ny: int = 0\nx, y = (1,)", "arity mismatch"),
        ("x: int = 0\ny: int = 0\nx, y = (1, 'a')", "element type mismatch"),
        ("x: int = 0\ny: int = 0\nx, y = [1, 2]", "typed tuple"),
        ("x: int = 0\ny: int = 0\n[x, y] = (1, 2)", "Only simple name assignments"),
        ("x: int = 0\ny: int = 0\nx, *y = (1, 2)", "plain named targets"),
        ("x: int = 0\ny: int = 0\n(x, (y,)) = (1, (2,))", "plain named targets"),
        ("x: int = 0\ny: int = 0\nx, y = (1, 2) = (3, 4)", "invalid syntax"),
        ("x: int = 0\ny: int = 0\nx, y = 1", "typed tuple"),
    ],
)
def test_rejects_beyond_bounded_unpack(source: str, message: str) -> None:
    if message == "invalid syntax":
        with pytest.raises(SyntaxError):
            PythonFrontend().parse(source)
    else:
        with pytest.raises(UnsupportedPython, match=message):
            PythonFrontend().parse(source)


def test_model_enforces_arity_type_and_references_independently() -> None:
    integer = Reference(Symbol("i", ValueType(ValueKind.INTEGER), "int"))
    text = Reference(Symbol("s", ValueType(ValueKind.STRING), "str"))
    with pytest.raises(ConstructError, match="arity mismatch"):
        UnpackAssign((integer, text), TupleValue((Literal(1),)))
    with pytest.raises(ConstructError, match="element type mismatch"):
        UnpackAssign((integer, text), TupleValue((Literal("hi"), Literal(1))))
    with pytest.raises(ConstructError, match="References"):
        UnpackAssign((Literal(1),), TupleValue((Literal(1),)))  # type: ignore[arg-type]
    with pytest.raises(ConstructError, match="typed tuple"):
        UnpackAssign((integer,), Literal(1))


def test_admission_requires_both_guarantees_before_rendering() -> None:
    node = _last("a: int = 1\nb: int = 2\na, b = b, a")
    assert any(
        decl.construct is UnpackAssign for decl in LANGUAGE_ADMISSION.declarations
    )

    @realizes(UnpackAssign)
    class NoGuarantees:
        template = "${value}"

    registry = RealizationRegistry("probe", (NoGuarantees,))
    with pytest.raises(ConstructError, match="assignment.unpack"):
        registry.recipe(node, EmitContext(registry))

    @realizes(UnpackAssign)
    class BothGuarantees:
        template = "${value}"
        supports = (
            "assignment.unpack.rhs_once_before_writes",
            "assignment.unpack.targets_left_to_right",
        )

    registry = RealizationRegistry("probe", (BothGuarantees,))
    assert registry.recipe(node, EmitContext(registry)).template == "${value}"


def test_nested_function_does_not_treat_outer_names_as_rebindable_locals() -> None:
    source = """
a: int = 1
b: int = 2
def exchange() -> None:
    a, b = b, a
"""
    with pytest.raises(UnsupportedPython, match="declared targets"):
        PythonFrontend().parse(source)


def test_unpack_can_bind_existing_typed_function_parameters() -> None:
    program = PythonFrontend().parse("""
def flip(a: int, b: int) -> int:
    a, b = b, a
    return a
""")
    function = program.body.children[0]
    assert isinstance(function, FunctionDefinition)
    statement = function.body.children[0]
    assert isinstance(statement, UnpackAssign)
    assert [item.symbol.name for item in statement.targets] == ["a", "b"]
