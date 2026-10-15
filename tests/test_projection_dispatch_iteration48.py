"""Iteration 48: projection admission and explicitly traversed unmatched Constructs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from pyinto import convert, realize
from pyinto.constructs import Block, Construct, ConstructError, Program
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)


class OutlineSession:
    def __init__(self) -> None:
        self.definitions: list[tuple[int, str, str]] = []

    def finish(self) -> list[tuple[int, str, str]]:
        return self.definitions


def _on_def(node: Construct, ctx: EmitContext) -> None:
    assert isinstance(node, lang.FunctionDefinition)
    assert isinstance(ctx.session, OutlineSession)
    assert ctx.current is node
    assert [type(n).__name__ for n in ctx.path[:3]] == [
        "Program",
        "Block",
        "FunctionDefinition",
    ]
    ctx.session.definitions.append(
        (len(ctx.path), node.signature.name, node.signature.return_type.annotation())
    )


@realizes(lang.FunctionDefinition)
class OnDef:
    visit = _on_def


class OutlinePack:
    target = "outline"
    dispatch = "structural"
    semantics = "projection"
    unhandled = "traverse"
    entries = (OnDef,)
    session = OutlineSession


def test_minimal_projection_target_needs_no_noop_visitors_or_false_supports() -> None:
    registry = RealizationRegistry.from_pack(OutlinePack)
    assert (registry.dispatch, registry.semantics, registry.unhandled) == (
        "structural",
        "projection",
        "traverse",
    )
    source = """\
def add(a: int, b: int) -> int:
    return a + b

def twice(x: int) -> int:
    return add(x, x)
"""
    assert convert(source, realizations=registry) == [
        (3, "add", "int"),
        (3, "twice", "int"),
    ]


def test_projection_does_not_require_runtime_supports_for_matched_visitors() -> None:
    class Session:
        def __init__(self) -> None:
            self.ops: list[str] = []

        def finish(self) -> list[str]:
            return self.ops

    def on_arithmetic(node: Construct, ctx: EmitContext) -> None:
        assert isinstance(ctx.session, Session)
        ctx.session.ops.append(type(node).__name__)

    @realizes(lang.Arithmetic)
    class OnArithmetic:
        visit = on_arithmetic

    registry = RealizationRegistry(
        "ops",
        (OnArithmetic,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        session_factory=Session,
    )
    # The rule requires evaluation.operands.left_to_right under preservation,
    # but a projection does not claim to reproduce the evaluation semantics.
    assert convert("x: int = 1 + 2", realizations=registry) == ["Arithmetic"]


def test_projection_unhandled_error_is_still_strict_when_not_opted_in() -> None:
    registry = RealizationRegistry(
        "outline",
        (OnDef,),
        dispatch="structural",
        semantics="projection",
        session_factory=OutlineSession,
    )
    with pytest.raises(ConstructError, match="No 'outline' realization for Program"):
        convert("def f() -> int:\n    return 1", realizations=registry)


def test_preservation_still_rejects_missing_contract_for_structural_visitor() -> None:
    class Collector:
        called: ClassVar[list[str]] = []

        def finish(self) -> list[str]:
            return self.called

    @realizes(lang.Arithmetic)
    class OnArithmetic:
        visit = lambda node, ctx: Collector.called.append("visited")

    # Use a full set of no-op visitors for the ancestor path to reach Arithmetic.
    @realizes(lang.Program)
    class OnProgram:
        visit = lambda node, ctx: None

    @realizes(lang.Block)
    class OnBlock:
        visit = lambda node, ctx: None

    @realizes(lang.Initialize)
    class OnInitialize:
        visit = lambda node, ctx: None

    registry = RealizationRegistry(
        "strict",
        (OnProgram, OnBlock, OnInitialize, OnArithmetic),
        dispatch="structural",
        session_factory=Collector,
    )
    assert registry.semantics == "preservation"
    assert registry.unhandled == "error"
    with pytest.raises(ConstructError, match="does not support contracts"):
        convert("x: int = 1 + 2", realizations=registry)
    assert not Collector.called


def test_projection_traverse_matches_exact_variant_not_fallback() -> None:
    class Session:
        def __init__(self) -> None:
            self.events: list[str] = []

        def finish(self) -> list[str]:
            return self.events

    @realizes(lang.Literal)
    class IntegerOnly:
        variant = "integer"
        visit = lambda node, ctx: ctx.session.events.append("integer")

    registry = RealizationRegistry(
        "selective",
        (IntegerOnly,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        session_factory=Session,
    )
    assert convert("x: str = 'a'\ny: int = 2", realizations=registry) == ["integer"]


def test_traverse_still_rejects_unregistered_construct_admission() -> None:
    @dataclass(frozen=True)
    class ForeignNode(Construct):
        HOLES: ClassVar[frozenset[str]] = frozenset()

    registry = RealizationRegistry.from_pack(OutlinePack)
    with pytest.raises(ConstructError, match="Unregistered Construct admission"):
        realize(Program(Block((ForeignNode(),))), realizations=registry)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"semantics": "invalid"}, "Invalid Target semantics mode"),
        ({"unhandled": "skip"}, "Invalid unhandled Construct policy"),
        ({"unhandled": "traverse"}, "needs structural dispatch and projection"),
        (
            {"dispatch": "structural", "unhandled": "traverse"},
            "needs structural dispatch and projection",
        ),
        (
            {"semantics": "projection", "unhandled": "traverse"},
            "needs structural dispatch and projection",
        ),
    ],
)
def test_invalid_registry_policy_combinations_rejected(
    options: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RealizationRegistry("bad", (), session_factory=OutlineSession, **options)


@pytest.mark.parametrize(
    ("semantic_mode", "unhandled_mode", "message"),
    [
        ("unsupported", "error", "Invalid Target semantics mode"),
        ("preservation", "nope", "Invalid unhandled Construct policy"),
        ("preservation", "traverse", "needs structural dispatch and projection"),
    ],
)
def test_invalid_pack_policy_combinations_rejected(
    semantic_mode: str, unhandled_mode: str, message: str
) -> None:
    class InvalidPack:
        target = "bad"
        dispatch = "structural"
        semantics = semantic_mode
        unhandled = unhandled_mode
        entries = ()
        session = OutlineSession

    with pytest.raises(ValueError, match=message):
        RealizationRegistry.from_pack(InvalidPack)


def test_projection_does_not_misroute_invalid_callback_or_hide_errors() -> None:
    class Session:
        def finish(self) -> None:
            return None

    @realizes(lang.FunctionDefinition)
    class BadVisitor:
        visit = lambda node, ctx: "illegal"

    registry = RealizationRegistry(
        "bad",
        (BadVisitor,),
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        session_factory=Session,
    )
    with pytest.raises(ConstructError, match="must return None"):
        convert("def f() -> int:\n    return 3", realizations=registry)


def test_legacy_composition_has_preservation_and_strict_defaults() -> None:
    from tests.support.c_realizer import c_bindings

    registry = c_bindings()
    assert registry.semantics == "preservation"
    assert registry.unhandled == "error"
    assert isinstance(convert("print('ok')", realizations=registry), str)


def test_projection_semantics_are_independent_of_composition_dispatch() -> None:
    @realizes(lang.Program)
    class ProgramTemplate:
        template = "${body}"

    @realizes(lang.Block)
    class BlockTemplate:
        template = "${children}"

    @realizes(lang.Initialize)
    class InitTemplate:
        template = "${name} = ${value}"

    @realizes(lang.Arithmetic)
    class AddTemplate:
        template = "${left} + ${right}"

    @realizes(lang.Literal)
    class NumberTemplate:
        variant = "integer"
        template = "1"

    entries = (
        ProgramTemplate,
        BlockTemplate,
        InitTemplate,
        AddTemplate,
        NumberTemplate,
    )
    projection = RealizationRegistry("projection-text", entries, semantics="projection")
    assert projection.dispatch == "composition"
    assert convert("x: int = 1 + 2", realizations=projection) == "x = 1 + 1\n"
    preservation = RealizationRegistry("preservation-text", entries)
    with pytest.raises(ConstructError, match="does not support contracts"):
        convert("x: int = 1 + 2", realizations=preservation)
