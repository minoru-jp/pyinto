"""Baseline acceptance checks for canonical specification CST / FRT / CMP IDs.

The Specification is authoritative; these focused checks guard edge cases
that previously depended mainly on end-to-end target tests.
"""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import (
    Branch,
    Break,
    Comparison,
    Construct,
    ConstructError,
    For,
    Literal,
    Range,
    Reference,
    While,
    With,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.realizations.registry import Composer, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import c_bindings


def _contains_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_ast(part) for part in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_contains_ast(getattr(value, f.name)) for f in fields(value))
    return False


def test_cst_003_frt_001_nested_source_normalizes_without_python_ast() -> None:
    source = (
        "item: int = 0\nlimit: int = 3\n"
        "for item in range(1, limit):\n"
        "    while item < limit:\n"
        "        if item == 1:\n"
        "            break\n"
        "        item = limit\n"
        "else:\n"
        "    print('normal')\n"
    )
    program = PythonFrontend().parse(source)
    loop = program.body.children[2]
    assert isinstance(loop, For)
    assert isinstance(loop.body.children[0], While)
    branch = loop.body.children[0].body.children[0]
    assert isinstance(branch, Branch)
    assert isinstance(branch.then_body.children[0], Break)
    assert isinstance(branch.condition, Comparison)
    assert isinstance(branch.condition.left, Reference)
    assert loop.parts()["entry"] is loop.entry
    assert loop.parts()["otherwise"] is loop.else_body
    assert loop.variant() == "with_else"
    assert not _contains_ast(program)


def test_cst_004_range_defaults_preserve_explicit_argument_structure() -> None:
    for args, expected in (
        ((Literal(4),), (0, 4, 1)),
        ((Literal(2), Literal(9)), (2, 9, 1)),
        ((Literal(2), Literal(9), Literal(-2)), (2, 9, -2)),
    ):
        node = Range(args)
        assert len(node.parts()) == len(args)
        assert tuple(value.value for value in node.bounds()) == expected
    with pytest.raises(ValueError, match="one to three"):
        Range(())
    with pytest.raises(ValueError, match="integers"):
        Range((Literal("x"),))


def test_cst_005_with_is_modelled_without_c_binding() -> None:
    program = PythonFrontend().parse(
        "resource: int = 1\nslot: int = 0\n"
        "with resource as slot:\n"
        "    print('inside')\n"
    )
    context = program.body.children[2]
    assert isinstance(context, With)
    assert len(context.entries) == 1
    assert context.entries[0].target is not None
    assert context.parts()["body"] is context.body
    with pytest.raises(ConstructError, match="No 'c' realization for With"):
        Composer(c_bindings()).source(program)


@pytest.mark.parametrize(
    "text, pattern",
    [
        (
            "item: int = 0\nfor item in range(2):\n    new: int = 5\nprint(new)",
            "Unresolved name",
        ),
        ("with 1 as missing:\n    print('ok')", "explicit prior type declaration"),
        ("break", "requires an enclosing loop"),
        ("continue", "requires an enclosing loop"),
    ],
)
def test_frt_003_rejects_unmodelled_bindings_or_exits(text: str, pattern: str) -> None:
    with pytest.raises(UnsupportedPython, match=pattern):
        PythonFrontend().parse(text)


def test_frt_006_frontend_reuse_does_not_leak_names() -> None:
    frontend = PythonFrontend()
    frontend.parse("old: int = 1")
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        frontend.parse("fresh: int = old")
    assert len(frontend.parse("fresh: int = 2").body.children) == 1


def test_cmp_002_slot_reuse_and_order_documented_contract() -> None:
    class Pair(Construct):
        HOLES = frozenset({"left", "right"})

        def parts(self) -> dict[str, object]:
            return {"left": Literal(1), "right": Literal(2)}

    visits: list[int] = []

    def choose_literal(node: Construct, ctx: object) -> str:
        assert isinstance(node, Literal)
        assert isinstance(node.value, int)
        visits.append(node.value)
        return str(node.value)

    @realizes(Pair)
    class PairRule:
        template = "${right}:${left}:${right}"

    @realizes(Literal)
    class LiteralRule:
        variant = "integer"
        render = choose_literal

    composer = Composer(
        RealizationRegistry("test", (PairRule, LiteralRule)),
        admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(Pair),)),
    )
    assert composer.source(Pair()) == "2:1:2\n"
    assert visits == [2, 1]


def test_cmp_003_missing_slot_fails_without_guessing() -> None:
    class OnlyLeaf(Construct):
        def parts(self) -> dict[str, object]:
            return {"left": Literal(1)}

    @realizes(OnlyLeaf)
    class BadRule:
        render = lambda node, ctx: "${missing}"

    composer = Composer(
        RealizationRegistry("test", (BadRule,)),
        admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(OnlyLeaf),)),
    )
    with pytest.raises(ConstructError, match="Unfilled template holes"):
        composer.source(OnlyLeaf())
