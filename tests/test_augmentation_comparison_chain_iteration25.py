"""Iteration 25: model-first scalar augmented rebinding and comparison chains.

The Frontend never executes source expressions, and neither Target Pack is
required to realize these new nodes. The admission check remains fail-closed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    AugAssign,
    AugAssignMode,
    Comparison,
    ComparisonChain,
    ConstructError,
    FieldRead,
    FloatingLiteral,
    Literal,
    Reference,
    ValueKind,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes, requires, supports, template
from tests.support.python_realizer.pack import python_bindings


def _last(source: str):
    return PythonFrontend().parse(source).body.children[-1]


def test_scalar_name_augmented_assignment_remains_one_statement() -> None:
    node = _last("x: int = 1\nx += 2")
    assert isinstance(node, AugAssign)
    assert node.target.symbol.name == "x"
    assert node.value == Literal(2)
    assert node.operator == "+"
    assert node.mode is AugAssignMode.REBIND
    assert tuple(node.parts()) == ("target", "op", "value")
    assert isinstance(_last("x: int = 7\nx //= 3"), AugAssign)
    assert isinstance(_last("x: int = 7\nx %= 3"), AugAssign)


def test_float_augassign_acceptance_is_strict_and_typed() -> None:
    node = _last("x: float = 1.0\nx /= 2.0")
    assert isinstance(node, AugAssign)
    assert node.target.kind is ValueKind.FLOAT
    assert node.value == FloatingLiteral(2.0)


CLASS = """
class Bucket:
    def __init__(self, count: int) -> None:
        self.count: int = count
    def add(self, step: int) -> None:
        self.count += step
b: Bucket = Bucket(1)
b.count += 2
"""


def test_augassign_to_declared_instance_field_preserves_lvalue_receiver() -> None:
    program = PythonFrontend().parse(CLASS)
    cls = program.body.children[0]
    method = cls.methods[1]
    inner = method.body.children[0]
    outer = program.body.children[-1]
    assert isinstance(inner, AugAssign)
    assert isinstance(outer, AugAssign)
    assert isinstance(inner.target, FieldRead)
    assert isinstance(outer.target, FieldRead)
    assert isinstance(inner.target.receiver, Reference)
    assert inner.target.field.name == "count"
    assert inner.value.kind is ValueKind.INTEGER
    assert outer.target.receiver.symbol.name == "b"


def test_compound_field_receiver_is_stored_once_in_target() -> None:
    source = """
class Counter:
    def __init__(self) -> None:
        self.n: int = 0

def create() -> Counter:
    return Counter()

create().n += 1
"""
    node = _last(source)
    assert isinstance(node, AugAssign)
    assert isinstance(node.target, FieldRead)
    assert node.target.receiver.kind is ValueKind.INSTANCE
    assert node.parts()["target"] is node.target


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("x += 1", "declared name"),
        ("x: int = 1\nx += 1.0", "Unsupported scalar"),
        ("x: float = 1.0\nx //= 1.0", "Unsupported scalar"),
        ("x: int = 1\nx /= 2", "Unsupported scalar"),
        ("x: str = 'a'\nx += 'b'", "scalar int or float"),
        ("xs: list[int] = [1]\nxs += [2]", "scalar int or float"),
        ("xs: list[int] = [1]\nxs[0] += 1", "Only named scalar"),
        ("x: int = 1\nx **= 2", "Unsupported augmented assignment operator"),
        ("x: int = 1\nx @= 2", "Unsupported augmented assignment operator"),
        ("y: bool = 1 < 2 in [2]", "Unsupported chained comparison operator"),
        ("y: bool = 1 < 2.0 < 3", "matching scalar type"),
        ("y: bool = 1 < '2' < 3", "matching scalar type"),
        ("y: bool = 1 < 2 is 2", "Unsupported chained comparison operator"),
    ],
)
def test_unsupported_forms_reject_without_source_execution(
    source: str, error: str
) -> None:
    with pytest.raises(UnsupportedPython, match=error):
        PythonFrontend().parse(source)


def test_field_must_exist_and_be_initialized_before_augassign() -> None:
    with pytest.raises(UnsupportedPython, match="Undeclared instance field"):
        PythonFrontend().parse(CLASS.replace("b.count += 2", "b.unknown += 2"))
    with pytest.raises(
        UnsupportedPython, match="Typed fields must be initialized at the start"
    ):
        PythonFrontend().parse("""
class Box:
    def __init__(self) -> None:
        self.count += 1
        self.count: int = 0
""")


def test_comparison_chain_is_not_eager_binary_comparisons() -> None:
    node = _last("a: int = 0\nb: int = 3\nc: int = 10\nflag: bool = a < b <= c")
    assert node.value.kind is ValueKind.BOOLEAN
    chain = node.value
    assert isinstance(chain, ComparisonChain)
    assert chain.operators == ("<", "<=")
    assert tuple(item.symbol.name for item in chain.operands) == ("a", "b", "c")
    assert "operands" in chain.parts()
    assert all(not isinstance(value, Comparison) for value in chain.operands)


def test_chained_comparison_supports_three_or_more_operations_on_scalars() -> None:
    for source in (
        "b: bool = 0 < 1 <= 2 != 4",
        "b: bool = 0.0 < 1.0 <= 2.0",
        "b: bool = 'a' < 'b' < 'c'",
    ):
        node = _last(source)
        assert isinstance(node.value, ComparisonChain)
        assert len(node.value.operands) == len(node.value.operators) + 1
    assert isinstance(_last("b: bool = 1 < 2").value, Comparison)


def test_chained_comparison_keeps_all_expression_nodes_without_duplication() -> None:
    source = """
def bump(n: int) -> int:
    return n + 1
flag: bool = bump(0) < bump(1) < bump(2)
"""
    chain = _last(source).value
    assert isinstance(chain, ComparisonChain)
    assert len(chain.operands) == 3
    assert chain.operands[1] is chain.parts()["operands"][1]


def test_model_construction_validates_operators_types_and_effects() -> None:
    with pytest.raises(ConstructError, match="at least three"):
        ComparisonChain((Literal(1), Literal(2)), ("<",))
    with pytest.raises(ConstructError, match="matching operators"):
        ComparisonChain((Literal(1), Literal(2), Literal(3)), ("<",))
    with pytest.raises(ConstructError, match="Unsupported chained"):
        ComparisonChain((Literal(1), Literal(2), Literal(3)), ("<", "in"))
    with pytest.raises(ConstructError, match="matching scalar type"):
        ComparisonChain((Literal(1), Literal("2"), Literal(3)), ("<", "<"))
    with pytest.raises(ConstructError, match="rebinding"):
        AugAssign(
            _last("x: int = 1\nx += 1").target, "+", Literal(1), AugAssignMode.IN_PLACE
        )
    with pytest.raises(ConstructError, match="Unsupported scalar"):
        AugAssign(_last("x: int = 1\nx += 1").target, "/", Literal(1))
    with pytest.raises(FrozenInstanceError):
        chain = ComparisonChain((Literal(1), Literal(2), Literal(3)), ("<", "<"))
        chain.operators = (">", ">")  # type: ignore[misc]


def test_provider_admission_keys_are_independent_of_target() -> None:
    augmented = _last("n: int = 1\nn += 2")
    chain = _last("b: bool = 0 < 1 < 2").value
    assert required_contracts(augmented) == {
        "assignment.augmented.target_once",
        "assignment.augmented.read_before_rhs",
        "assignment.augmented.rebind",
    }
    assert required_contracts(chain) == {
        "comparison.chain.operands_once",
        "comparison.chain.short_circuit",
        "comparison.chain.left_to_right",
    }


@pytest.mark.parametrize("kind", ["augassign", "chain"])
def test_admission_rejects_before_recipe_side_effects(kind: str) -> None:
    node = (
        _last("n: int = 1\nn += 2")
        if kind == "augassign"
        else _last("b: bool = 1 < 2 < 3").value
    )
    events: list[str] = []

    @realizes(type(node))
    class Unsafe:
        requires @= "should-not-be-added.h"
        template @= "unsafe"

    registry = RealizationRegistry("test", (Unsafe,))
    context = EmitContext(registry)
    with pytest.raises(ConstructError, match="does not support contracts"):
        registry.recipe(node, context)
    assert context.headers == set()
    assert events == []
    with pytest.raises(ConstructError):
        from pyinto import realize

        realize(node, realizations=python_bindings())


def test_rebinding_admission_is_explicit_and_never_inherited() -> None:
    node = _last("n: int = 1\nn += 2")

    @realizes(AugAssign)
    class Partial:
        template @= "${target} += ${value}"
        supports @= ("assignment.augmented.target_once",)

    registry = RealizationRegistry("test", (Partial,))
    with pytest.raises(ConstructError, match="assignment.augmented"):
        registry.recipe(node, EmitContext(registry))
