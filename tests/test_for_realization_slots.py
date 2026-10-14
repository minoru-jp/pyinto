"""SDD phase 4: For stays a pure Model; Realization supplies extra Slots."""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, realize
from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import (
    Block,
    Construct,
    ConstructError,
    For,
    IterationEntry,
    Literal,
    Program,
    Range,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.realizations.layout import TemplatePlan
from pyinto.realizations.registry import Composer, RealizationRegistry
from pyinto.realizations.regulation import realizes, render, variant
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings
from tests.test_construct_pipeline import run_c


def _loop(*args: int, with_else: bool = False) -> For:
    symbol = Symbol("item", ValueType(ValueKind.INTEGER), "int")
    return For(
        IterationEntry(Reference(symbol), Range(tuple(Literal(i) for i in args))),
        Block(()),
        Block(()) if with_else else None,
    )


@pytest.mark.parametrize("args", [(5,), (2, 5), (1, 9, 2)])
@pytest.mark.parametrize("with_else", [False, True])
def test_cst_009_for_parts_are_independent_of_range_projection(
    args: tuple[int, ...], with_else: bool
) -> None:
    loop = _loop(*args, with_else=with_else)
    expected = {"entry": loop.entry, "body": loop.body}
    if with_else:
        expected["otherwise"] = loop.else_body
    assert loop.parts() == expected
    assert not {"start", "stop", "step", "target"} & loop.HOLES
    assert isinstance(loop.entry.iterable, Range)
    assert tuple(v.value for v in loop.entry.iterable.bounds()) == (
        (0, args[0], 1)
        if len(args) == 1
        else (args[0], args[1], 1)
        if len(args) == 2
        else args
    )


def test_cst_009_non_range_for_is_still_a_valid_construct() -> None:
    symbol = Symbol("item", ValueType(ValueKind.INTEGER), "int")
    iterable = Reference(
        Symbol("items", ValueType(ValueKind.ITERABLE), "Iterable[int]")
    )
    loop = For(IterationEntry(Reference(symbol), iterable), Block(()))
    assert loop.parts() == {"entry": loop.entry, "body": loop.body}
    assert "for item in items:" in realize(loop, realizations=python_bindings())
    with pytest.raises(ConstructError, match=r"iteration\.source\.(?:iterable|string)"):
        realize(loop, realizations=c_bindings())


@pytest.mark.parametrize(
    "source, expected",
    [
        ("item: int = 0\nfor item in range(3):\n    print('x')", b"x\nx\nx\n"),
        ("item: int = 0\nfor item in range(2, 5):\n    print('y')", b"y\ny\ny\n"),
        (
            "item: int = 0\nfor item in range(5, 0, -2):\n    print('z')\n"
            + "else:\n    print('done')",
            b"z\nz\nz\ndone\n",
        ),
    ],
)
def test_cmp_010_c_binding_supplies_range_slots_without_mutation(
    source: str, expected: bytes, tmp_path: object
) -> None:
    program = PythonFrontend().parse(source)
    loop = program.body.children[1]
    assert isinstance(loop, For)
    before = loop.parts().copy()
    c_source = realize(program, realizations=c_bindings())
    assert loop.parts() == before
    assert "sk_range_" in c_source
    assert "long long" in c_source
    assert run_c(c_source, tmp_path).stdout == expected  # type: ignore[arg-type]
    assert "for item in range(" in realize(program, realizations=python_bindings())


class _Example(Construct):
    def parts(self) -> dict[str, object]:
        return {"body": Literal(7)}


@realizes(_Example)
class _ExampleRule:
    render @= lambda node, ctx: TemplatePlan(
        "${prefix}-${body}-${prefix}", {"prefix": Literal(3)}
    )


@realizes(Literal)
class _LiteralRule:
    variant @= "integer"
    render @= lambda node, ctx: str(node.value)


def test_cmp_010_realization_slots_are_recursive_and_reused() -> None:
    assert (
        Composer(
            RealizationRegistry("test", (_ExampleRule, _LiteralRule)),
            admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(_Example),)),
        ).source(_Example())
        == "3-7-3\n"
    )


@pytest.mark.parametrize(
    "extra, source, message",
    [
        ({"body": Literal(1)}, "${body}", "cannot replace Model parts"),
        ({"unused": Literal(1)}, "${body}", "Unused Realization slots"),
        ({}, "${body}${missing}", "Unfilled template holes"),
    ],
)
def test_cmp_010_invalid_realization_slot_mapping_rejected(
    extra: dict[str, object], source: str, message: str
) -> None:
    def select(node: Construct, ctx: object) -> TemplatePlan:
        return TemplatePlan(source, extra)

    @realizes(_Example)
    class Rule:
        render @= select

    with pytest.raises(ConstructError, match=message):
        Composer(
            RealizationRegistry("test", (Rule, _LiteralRule)),
            admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(_Example),)),
        ).source(_Example())


def test_cmp_010_composer_owned_requirements_cannot_be_replaced() -> None:
    @realizes(Program)
    class BadProgram:
        render @= lambda node, ctx: TemplatePlan(
            "${requirements}", {"requirements": Literal(123)}
        )

    with pytest.raises(ConstructError, match="cannot replace Model parts"):
        Composer(RealizationRegistry("test", (BadProgram,))).source(Program(Block(())))
