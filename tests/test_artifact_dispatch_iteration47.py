"""Target-owned artifacts and two declaration-selected Realizer call chains."""

from __future__ import annotations

from typing import ClassVar

import pytest

from pyinto import convert, realize
from pyinto.constructs import (
    Block,
    ConstructError,
    ExpressionStatement,
    Literal,
    Program,
)
from pyinto.frontend import PythonFrontend
from pyinto.interfaces import language as lang
from pyinto.realizations.artifacts import TextArtifactSession
from pyinto.realizations.host import RealizationHost
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


class ArtifactCollector:
    """Never constructs text: keeps a Target-specific object until finish."""

    def __init__(self) -> None:
        self.nodes: list[tuple[str, tuple[str, ...], str | None]] = []
        self.finished = False

    def finish(self) -> dict[str, object]:
        assert not self.finished
        self.finished = True
        return {"nodes": self.nodes, "encoding": b"\x00\xfe"}


def _record(node: object, ctx: EmitContext) -> None:
    assert isinstance(ctx.session, ArtifactCollector)
    assert ctx.current is node
    assert ctx.path[0] is ctx.root
    ctx.session.nodes.append(
        (
            type(node).__name__,
            tuple(type(part).__name__ for part in ctx.path),
            type(ctx.parent).__name__ if ctx.parent is not None else None,
        )
    )


@realizes(lang.Program)
class ProgramVisitor:
    visit = _record


@realizes(lang.Block)
class BlockVisitor:
    visit = _record


@realizes(lang.Initialize)
class InitializeVisitor:
    visit = _record


@realizes(lang.Literal)
class LiteralVisitor:
    variant = "integer"
    visit = _record


class StructuredPack:
    target = "structure"
    entries = (ProgramVisitor, BlockVisitor, InitializeVisitor, LiteralVisitor)
    dispatch = "structural"
    session = ArtifactCollector


def test_structural_dispatch_preorder_context_and_arbitrary_artifacts() -> None:
    registry = RealizationRegistry.from_pack(StructuredPack)
    result = convert("x: int = 1\ny: int = 2", realizations=registry)
    assert result == {
        "nodes": [
            ("Program", ("Program",), None),
            ("Block", ("Program", "Block"), "Program"),
            ("Initialize", ("Program", "Block", "Initialize"), "Block"),
            ("Literal", ("Program", "Block", "Initialize", "Literal"), "Initialize"),
            ("Initialize", ("Program", "Block", "Initialize"), "Block"),
            ("Literal", ("Program", "Block", "Initialize", "Literal"), "Initialize"),
        ],
        "encoding": b"\x00\xfe",
    }
    assert convert("x: int = 1", realizations=registry) == {
        "nodes": result["nodes"][:4],  # type: ignore[index]
        "encoding": b"\x00\xfe",
    }


def test_structural_visits_shared_construct_once_per_occurrence() -> None:
    @realizes(lang.ExpressionStatement)
    class ExpressionVisitor:
        visit = _record

    registry = RealizationRegistry(
        "structure",
        (ProgramVisitor, BlockVisitor, ExpressionVisitor, LiteralVisitor),
        dispatch="structural",
        session_factory=ArtifactCollector,
    )
    shared = Literal(5)
    program = Program(Block((ExpressionStatement(shared), ExpressionStatement(shared))))
    artifact = realize(program, realizations=registry)
    assert isinstance(artifact, dict)
    assert [entry[0] for entry in artifact["nodes"]] == [
        "Program",
        "Block",
        "ExpressionStatement",
        "Literal",
        "ExpressionStatement",
        "Literal",
    ]


def test_admission_checks_structural_contracts_before_visit_or_finish() -> None:
    class TrackingSession(ArtifactCollector):
        calls: ClassVar[list[str]] = []

        def finish(self) -> dict[str, object]:
            self.calls.append("finish")
            return super().finish()

    @realizes(lang.For)
    class UnsupportedFor:
        visit = _record

    registry = RealizationRegistry(
        "structure",
        (
            ProgramVisitor,
            BlockVisitor,
            InitializeVisitor,
            LiteralVisitor,
            UnsupportedFor,
        ),
        dispatch="structural",
        session_factory=TrackingSession,
    )
    source = "i: int = 0\nfor i in range(2):\n    print('x')"
    with pytest.raises(ConstructError, match="does not support contracts"):
        convert(source, realizations=registry)
    assert not TrackingSession.calls


def test_structural_requires_explicit_realization_for_every_construct() -> None:
    class IncompletePack:
        target = "incomplete"
        entries = (ProgramVisitor,)
        dispatch = "structural"
        session = ArtifactCollector

    with pytest.raises(ConstructError, match="No 'incomplete' realization for Block"):
        convert(
            "x: int = 1", realizations=RealizationRegistry.from_pack(IncompletePack)
        )


def test_structural_visitor_must_not_return_artifact_fragments() -> None:
    @realizes(lang.Program)
    class Bad:
        visit = lambda node, ctx: "not permitted"

    registry = RealizationRegistry(
        "bad", (Bad,), dispatch="structural", session_factory=ArtifactCollector
    )
    with pytest.raises(ConstructError, match="must return None"):
        realize(PythonFrontend().parse(""), realizations=registry)


def test_dispatch_mode_declaration_rejects_incompatible_entries() -> None:
    @realizes(lang.Program)
    class ProgramTemplate:
        template = "${body}"

    with pytest.raises(ValueError, match="dispatch does not match"):
        RealizationRegistry(
            "invalid",
            (ProgramTemplate,),
            dispatch="structural",
            session_factory=ArtifactCollector,
        )
    with pytest.raises(ValueError, match="dispatch does not match"):
        RealizationRegistry("invalid", (ProgramVisitor,))
    with pytest.raises(ValueError, match="needs an artifact session"):
        RealizationRegistry("invalid", (), dispatch="structural")


@pytest.mark.parametrize("mode", ["invalid", "", "STRUCTURAL"])
def test_invalid_pack_modes_rejected(mode: str) -> None:
    class BadPack:
        target = "bad"
        entries = ()
        dispatch = mode
        session = ArtifactCollector

    with pytest.raises(ValueError, match="Invalid Target dispatch mode"):
        RealizationRegistry.from_pack(BadPack)


def test_missing_structural_session_rejected_by_pack() -> None:
    class BadPack:
        target = "bad"
        entries = ()
        dispatch = "structural"

    with pytest.raises(ValueError, match="needs an artifact session"):
        RealizationRegistry.from_pack(BadPack)


def test_composition_is_unchanged_and_artifact_owned_by_target() -> None:
    class CustomTextSession(TextArtifactSession):
        calls: ClassVar[list[tuple[str, ...]]] = []

        def accept_composition(self, layout: object, context: EmitContext) -> None:
            self.calls.append(tuple(sorted(context.headers)))
            super().accept_composition(layout, context)  # type: ignore[arg-type]

        def finish(self) -> bytes:
            return super().finish().encode("utf-8")

    @realizes(lang.Program)
    class ProgramTemplate:
        template = "${body}"

    @realizes(lang.Block)
    class BlockTemplate:
        template = "${children}"

    @realizes(lang.Initialize)
    class InitializeTemplate:
        template = "${name} = ${value}"

    @realizes(lang.Literal)
    class LiteralTemplate:
        variant = "integer"
        template = "1"

    registry = RealizationRegistry(
        "bytes",
        (ProgramTemplate, BlockTemplate, InitializeTemplate, LiteralTemplate),
        session_factory=CustomTextSession,
    )
    root = PythonFrontend().parse("x: int = 1")
    assert realize(root, realizations=registry) == b"x = 1\n"
    assert Composer(registry).source(root) == "x = 1\n"
    assert CustomTextSession.calls == [()]


def test_composition_with_existing_targets_and_target_pack_metadata() -> None:
    for registry in (c_bindings(), python_bindings()):
        assert registry.dispatch == "composition"
        assert registry.session_factory is TextArtifactSession
        output = convert("print('ok')", realizations=registry)
        assert isinstance(output, str)
        assert "ok" in output


def test_session_contract_checked_before_dispatched_callbacks() -> None:
    class BadSession:
        def finish(self) -> str:
            return "bad"

    registry = RealizationRegistry(
        "bad", (), dispatch="composition", session_factory=BadSession
    )
    with pytest.raises(TypeError, match="accept_composition"):
        RealizationHost(registry).run(PythonFrontend().parse(""))
