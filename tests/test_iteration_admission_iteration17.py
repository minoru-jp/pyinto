"""Iteration types are checked before Model construction or Target emission."""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Block,
    ConstructError,
    For,
    IterationEntry,
    Literal,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.realizations.registry import Composer, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def loop(source: str) -> For:
    program = PythonFrontend().parse(source)
    for child in program.body.children:
        if isinstance(child, For):
            return child
    raise AssertionError("Expected for loop")


@pytest.mark.parametrize(
    "source, kind",
    [
        ("i: int = 0\nfor i in range(2):\n    print('ok')", "range"),
        ("s: str = ''\nfor s in 'ab':\n    print('ok')", "string"),
        (
            "xs: list[int] = [1, 2]\ni: int = 0\nfor i in xs:\n    print('ok')",
            "list",
        ),
        (
            "xs: tuple[int, int] = (1, 2)\ni: int = 0\nfor i in xs:\n    print('ok')",
            "tuple",
        ),
        (
            "xs: tuple[int, str] = (1, 'a')\ni: object = 0\nfor i in xs:\n    print('ok')",
            "tuple",
        ),
    ],
)
def test_accepted_source_and_target_types(source: str, kind: str) -> None:
    node = loop(source)
    assert required_contracts(node) == frozenset(
        {f"iteration.source.{kind}", "loop.for.break_continue"}
    )
    assert required_contracts(node.entry) == {f"iteration.source.{kind}"}


@pytest.mark.parametrize(
    "source, message",
    [
        ("i: int = 0\nn: int = 1\nfor i in n:\n    print('ok')", "iteration source"),
        (
            "i: int = 0\nf: float = 1.0\nfor i in f:\n    print('ok')",
            "iteration source",
        ),
        (
            "i: int = 0\nb: bool = True\nfor i in b:\n    print('ok')",
            "iteration source",
        ),
        (
            "d: dict[str, int] = {'a': 1}\ns: str = ''\nfor s in d:\n    print('ok')",
            "iteration source",
        ),
        ("s: str = ''\nfor s in range(3):\n    print('ok')", "target type mismatch"),
        ("i: int = 0\nfor i in 'hi':\n    print('ok')", "target type mismatch"),
        (
            "xs: list[str] = ['a']\ni: int = 0\nfor i in xs:\n    print('ok')",
            "target type mismatch",
        ),
        (
            "xs: tuple[int, str] = (1, 'a')\ni: int = 0\nfor i in xs:\n    print('ok')",
            "target type mismatch",
        ),
    ],
)
def test_frontend_rejects_incompatible_iteration(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend().parse(source)


def test_target_pack_acceptance_uses_source_kind() -> None:
    range_loop = loop("i: int = 0\nfor i in range(2):\n    print('ok')")
    string_loop = loop("s: str = ''\nfor s in 'ab':\n    print('ok')")
    assert "for i in range(2):" in realize(range_loop, realizations=python_bindings())
    assert "for s in 'ab':" in realize(string_loop, realizations=python_bindings())
    assert "sk_range_" in realize(range_loop, realizations=c_bindings())
    with pytest.raises(ConstructError, match="iteration.source.string"):
        realize(string_loop, realizations=c_bindings())


def test_admission_rejects_before_rendering_or_side_effects() -> None:
    events: list[str] = []

    def unsafe_render(node: For, context: object) -> str:
        events.append("rendered")
        return "for ${entry}: ${body}"

    @realizes(For)
    class OnlyRange:
        supports = ("iteration.source.range",)
        render = unsafe_render

    target = Reference(Symbol("i", ValueType(ValueKind.STRING), "str"))
    non_range = For(IterationEntry(target, Literal("hello")), Block(()))
    with pytest.raises(ConstructError, match="iteration.source.string"):
        Composer(RealizationRegistry("dummy", (OnlyRange,))).source(non_range)
    assert not events


def test_unshaped_iterable_stays_a_model_but_requires_support() -> None:
    symbol = Symbol("item", ValueType(ValueKind.INTEGER), "int")
    source = Reference(Symbol("items", ValueType(ValueKind.ITERABLE), "Iterable"))
    node = For(IterationEntry(Reference(symbol), source), Block(()))
    assert "iteration.source.iterable" in required_contracts(node)
    assert "for item in items:" in realize(node, realizations=python_bindings())
    with pytest.raises(ConstructError, match="iteration.source.iterable"):
        realize(node, realizations=c_bindings())


def test_unsupported_manual_source_is_never_admitted_by_standard_packs() -> None:
    symbol = Symbol("i", ValueType(ValueKind.INTEGER), "int")
    node = For(IterationEntry(Reference(symbol), Literal(3)), Block(()))
    assert "iteration.source.unsupported" in required_contracts(node)
    for registry in (c_bindings(), python_bindings()):
        with pytest.raises(ConstructError, match="iteration.source.unsupported"):
            realize(node, realizations=registry)
