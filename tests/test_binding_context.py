"""Target Bindings can read surrounding structure without modifying Constructs."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pyinto import PythonFrontend
from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import (
    Block,
    Branch,
    Break,
    Comparison,
    Construct,
    ConstructError,
    Initialize,
    Literal,
    Program,
    Reference,
    While,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.realizations import Composer, RealizationRegistry
from pyinto.realizations.layout import Text
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import C_DECLARATIONS, c_bindings


def test_binding_can_read_root_ancestors_parent_and_sibling_contracts() -> None:
    program = PythonFrontend().parse(
        "n: int = 0\nwhile n < 2:\n    if n == 1:\n        break\n    n = 2"
    )
    declaration, loop = program.body.children
    assert isinstance(declaration, Initialize)
    assert isinstance(loop, While)
    branch = loop.body.children[0]
    assert isinstance(branch, Branch)

    visited: list[Break] = []

    def select_break(node: Construct, ctx: object) -> str:
        from pyinto.realizations.registry import EmitContext

        assert isinstance(ctx, EmitContext)
        assert isinstance(node, Break)
        assert ctx.current is node
        assert ctx.root is program
        assert ctx.ancestors == (
            program,
            program.body,
            loop,
            loop.body,
            branch,
            branch.then_body,
        )
        assert ctx.path == (*ctx.ancestors, node)
        assert ctx.parent is branch.then_body
        assert isinstance(ctx.root, Program)
        # A Binding may inspect siblings and their type/mapped declarations.
        assert ctx.root.body.children[0] is declaration
        assert declaration.symbol.annotation == "int"
        assert isinstance(branch.condition, Comparison)
        assert isinstance(branch.condition.left, Reference)
        assert branch.condition.left.symbol is declaration.symbol
        visited.append(node)
        return "break;"

    @realizes(Break)
    class InspectBreak:
        render = select_break

    entries = tuple(entry for entry in C_DECLARATIONS if entry.__name__ != "CBreak")
    bindings = RealizationRegistry("c", (*entries, InspectBreak))
    composer = Composer(bindings)
    first = composer.source(program)
    assert len(visited) == 1
    assert composer.context.root is program
    assert composer.context.path == ()
    assert composer.context.current is None
    assert composer.context.parent is None
    assert composer.context.ancestors == ()
    assert composer.source(program) == first
    assert len(visited) == 2
    # No rewrites of the original structural nodes were required.
    assert program.body.children == (declaration, loop)
    assert "break;" in first


def test_root_of_direct_subtree_is_the_composition_root() -> None:
    root = Literal(7)
    composer = Composer(c_bindings())
    assert composer.source(root) == "7LL\n"
    assert composer.context.root is root
    assert composer.context.path == ()


@dataclass(frozen=True)
class _Leaf(Construct):
    name: str


@dataclass(frozen=True)
class _Pair(Construct):
    left: _Leaf
    right: _Leaf

    HOLES = frozenset({"left", "right"})

    def parts(self) -> dict[str, object]:
        return {"left": self.left, "right": self.right}


def test_slots_compose_once_in_template_order_with_fresh_emission_state() -> None:
    root = _Pair(_Leaf("left"), _Leaf("right"))
    visited: list[tuple[str, tuple[Construct, ...]]] = []

    def select_leaf(node: Construct, ctx: object) -> Text:
        from pyinto.realizations.registry import EmitContext

        assert isinstance(ctx, EmitContext)
        assert isinstance(node, _Leaf)
        assert ctx.root is root
        assert ctx.parent is root
        visited.append((node.name, ctx.path))
        return Text(f"{node.name}={ctx.fresh('slot')}")

    @realizes(_Pair)
    class PairBinding:
        render = lambda node, ctx: "${right}|${left}|${right}"

    @realizes(_Leaf)
    class LeafBinding:
        render = select_leaf

    composer = Composer(
        RealizationRegistry("c", (PairBinding, LeafBinding)),
        admission=LANGUAGE_ADMISSION.extend(
            (AdmissionDeclaration(_Pair), AdmissionDeclaration(_Leaf))
        ),
    )
    expected = "right=sk_slot_0|left=sk_slot_1|right=sk_slot_0\n"
    assert composer.source(root) == expected
    assert composer.source(root) == expected
    assert visited == [
        ("right", (root, root.right)),
        ("left", (root, root.left)),
        ("right", (root, root.right)),
        ("left", (root, root.left)),
    ]
    assert root.left.name == "left" and root.right.name == "right"


def test_context_path_restored_when_binding_rejects_a_node() -> None:
    def reject(node: Construct, ctx: object) -> str:
        from pyinto.realizations.registry import EmitContext

        assert isinstance(ctx, EmitContext)
        assert ctx.current is node
        raise ConstructError("intentionally unsupported")

    @realizes(Literal)
    class RejectLiteral:
        variant = "integer"
        render = reject

    entries = tuple(
        entry for entry in C_DECLARATIONS if entry.__name__ != "CIntegerLiteral"
    )
    composer = Composer(RealizationRegistry("c", (*entries, RejectLiteral)))
    with pytest.raises(ConstructError, match="intentionally unsupported"):
        composer.source(Block((Literal(1),)))
    assert composer.context.path == ()
    assert composer.context.current is None
    assert composer.context.ancestors == ()


def test_independent_compositions_do_not_leak_headers_or_root() -> None:
    composer = Composer(c_bindings())
    with_print = PythonFrontend().parse('print("hello")')
    empty = Program(Block(()))
    assert "#include <stdio.h>" in composer.source(with_print)
    assert composer.context.root is with_print
    no_print = composer.source(empty)
    assert "#include <stdio.h>" not in no_print
    assert composer.context.root is empty
