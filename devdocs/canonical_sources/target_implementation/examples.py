"""Runnable code examples embedded verbatim into canonical Target guides.

Ordinary tests execute these snippets. They are examples, not shipped Targets.
"""

STRUCTURAL_EXAMPLE = """\
from pyinto import convert
from pyinto.constructs import Construct
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    pack_dispatch, pack_entries, pack_semantics, pack_session,
    pack_target, pack_unhandled, realizes, visit,
)


class OutlineSession:
    def __init__(self):
        self.names = []

    def finish(self):
        return self.names


def collect(node: Construct, ctx: EmitContext) -> None:
    assert isinstance(node, lang.FunctionDefinition)
    assert isinstance(ctx.session, OutlineSession)
    ctx.session.names.append(
        (node.signature.name, node.signature.return_type.annotation())
    )


@realizes(lang.FunctionDefinition)
class FunctionOutline:
    visit @= collect


class OutlinePack:
    pack_target @= "outline"
    pack_dispatch @= "structural"
    pack_semantics @= "projection"
    pack_unhandled @= "traverse"
    pack_session @= OutlineSession
    pack_entries @= (FunctionOutline,)


registry = RealizationRegistry.from_pack(OutlinePack)
source = "def add(a: int, b: int) -> int:\\n    return a + b\\n"
assert convert(source, realizations=registry) == [("add", "int")]
"""

COMPOSITION_EXAMPLE = """\
from pyinto import realize
from pyinto.constructs import Block, ExpressionStatement, Literal, Program
from pyinto.interfaces import language as lang
from pyinto.realizations import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import (
    pack_dispatch, pack_entries, pack_session, pack_target,
    realizes, render, template, variant,
)


@realizes(lang.Program)
class ProgramRule:
    template @= "${body}"


@realizes(lang.Block)
class BlockRule:
    template @= "${children}"


@realizes(lang.ExpressionStatement)
class ExpressionRule:
    template @= "${expression};"


def integer(node, ctx):
    assert isinstance(node, lang.Literal)
    return str(node.value)


@realizes(lang.Literal)
class IntegerRule:
    variant @= "integer"
    render @= integer


class TextPack:
    pack_target @= "demotext"
    pack_dispatch @= "composition"
    pack_session @= TextArtifactSession
    pack_entries @= (ProgramRule, BlockRule, ExpressionRule, IntegerRule)


registry = RealizationRegistry.from_pack(TextPack)
model = Program(Block((ExpressionStatement(Literal(2)),)))
assert realize(model, realizations=registry) == "2;\\n"
"""
