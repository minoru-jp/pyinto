"""Iteration 49: explicit variant domains, projection omissions and wildcard dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from pyinto import convert
from pyinto.constructs import Construct, ConstructError, IntrinsicCall, Literal
from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes, template, variant, visit


class Collector:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str]] = []

    def finish(self) -> list[tuple[str, str]]:
        return self.seen


def collect(node: Construct, ctx: EmitContext) -> None:
    assert isinstance(ctx.session, Collector)
    ctx.session.seen.append((type(node).__name__, node.variant()))


def projection(*entries: type[object]) -> RealizationRegistry:
    return RealizationRegistry(
        "probe",
        entries,
        dispatch="structural",
        semantics="projection",
        unhandled="traverse",
        session_factory=Collector,
    )


def test_published_variant_domains_are_exact_and_stable() -> None:
    expected = {
        lang.Literal: {"integer", "string"},
        lang.Return: {"default", "with_value"},
        lang.Branch: {"default", "with_else"},
        builtin.Range: {"1", "2", "3"},
        lang.Try: {"handlers", "finally", "handlers_finally"},
        lang.BooleanLiteral: {"true", "false"},
        lang.SliceValue: {"list", "string"},
        lang.Membership: {"list_in", "list_not_in", "dict_in", "dict_not_in"},
    }
    for kind, domain in expected.items():
        assert kind.variant_domain() == frozenset(domain)
    assert lang.Program.variant_domain() == frozenset({"default"})
    assert IntrinsicCall.variant_domain() is None


@pytest.mark.parametrize("kind", [lang.Literal, lang.Branch, lang.Return, lang.Try])
@pytest.mark.parametrize("mode", ["composition", "structural"])
def test_unknown_variant_is_rejected_on_registration(
    kind: type[Construct], mode: str
) -> None:
    if mode == "structural":

        @realizes(kind)
        class StructuralBad:
            variant @= "no_such_variant"
            visit @= collect

        candidate = StructuralBad
    else:

        @realizes(kind)
        class CompositionBad:
            variant @= "no_such_variant"
            template @= "x"

        candidate = CompositionBad
    with pytest.raises(ValueError, match="invalid variant 'no_such_variant'"):
        RealizationRegistry(
            "bad",
            (candidate,),
            dispatch=mode,
            semantics="projection" if mode == "structural" else "preservation",
            session_factory=Collector if mode == "structural" else None,
        )


def test_literal_omission_rejected_even_in_composition() -> None:
    @realizes(lang.Literal)
    class ImplicitDefault:
        template @= "ignored"

    with pytest.raises(ValueError, match="invalid variant 'default'"):
        RealizationRegistry("mistake", (ImplicitDefault,))


def test_multivariant_return_omission_rejected_in_structural_projection() -> None:
    @realizes(lang.Return)
    class ImplicitDefault:
        visit @= collect

    with pytest.raises(ValueError, match="requires explicit variant"):
        projection(ImplicitDefault)


def test_explicit_return_variant_is_selective_and_does_not_require_coverage() -> None:
    @realizes(lang.Return)
    class BareOnly:
        variant @= "default"
        visit @= collect

    assert convert(
        "def f() -> None:\n    return", realizations=projection(BareOnly)
    ) == [("Return", "default")]
    assert (
        convert("def f() -> int:\n    return 2", realizations=projection(BareOnly))
        == []
    )


def test_wildcard_handles_all_variants_and_exact_rule_overrides() -> None:
    @realizes(lang.Literal)
    class AllLiterals:
        variant @= "*"
        visit @= collect

    @realizes(lang.Literal)
    class Integers:
        variant @= "integer"
        visit @= lambda node, ctx: ctx.session.seen.append(("override", node.variant()))

    assert convert(
        "x: int = 3\ny: str = 's'", realizations=projection(AllLiterals)
    ) == [("Literal", "integer"), ("Literal", "string")]
    assert convert(
        "x: int = 3\ny: str = 's'", realizations=projection(AllLiterals, Integers)
    ) == [("override", "integer"), ("Literal", "string")]
    assert convert(
        "x: int = 3\ny: str = 's'", realizations=projection(Integers, AllLiterals)
    ) == [("override", "integer"), ("Literal", "string")]


def test_wildcard_in_composition_and_duplicate_wildcard_rejected() -> None:
    @realizes(lang.Literal)
    class Both:
        variant @= "*"
        template @= "hello"

    @realizes(lang.Literal)
    class BothAgain:
        variant @= "*"
        template @= "different"

    registry = RealizationRegistry("text", (Both,))
    assert Composer(registry).source(Literal(1)) == "hello\n"
    assert Composer(registry).source(Literal("one")) == "hello\n"
    with pytest.raises(ValueError, match="Duplicate .* realization.*Literal:\\*"):
        RealizationRegistry("text", (Both, BothAgain))


def test_explicit_default_under_preservation_keeps_old_behavior() -> None:
    @realizes(lang.Return)
    class DefaultReturn:
        template @= "return"

    registry = RealizationRegistry("text", (DefaultReturn,))
    assert registry.has_recipe(lang.Return())
    assert not registry.has_recipe(lang.Return(Literal(3)))


def test_wildcard_does_not_bypass_preservation_admission() -> None:
    @realizes(lang.Arithmetic)
    class EveryArithmetic:
        variant @= "*"
        template @= "${left} + ${right}"

    @realizes(lang.Program)
    class Program:
        template @= "${body}"

    @realizes(lang.Block)
    class Block:
        template @= "${children}"

    @realizes(lang.Initialize)
    class Initialize:
        template @= "${value}"

    @realizes(lang.Literal)
    class LiteralRule:
        variant @= "*"
        template @= "1"

    registry = RealizationRegistry(
        "text", (Program, Block, Initialize, EveryArithmetic, LiteralRule)
    )
    with pytest.raises(ConstructError, match="does not support contracts"):
        convert("x: int = 1 + 2", realizations=registry)


def test_open_domains_allow_explicit_keys_and_wildcards() -> None:
    @realizes(lang.IntrinsicCall)
    class Open:
        variant @= "custom.provider.operation"
        visit @= collect

    @realizes(lang.IntrinsicCall)
    class All:
        variant @= "*"
        visit @= collect

    registry = projection(Open, All)
    assert registry.semantics == "projection"
    assert registry.unhandled == "traverse"


def test_custom_dynamic_construct_without_domain_is_open() -> None:
    @dataclass(frozen=True)
    class Custom(Construct):
        HOLES: ClassVar[frozenset[str]] = frozenset()

        def variant(self) -> str:
            return "vendor-specific"

    assert Custom.variant_domain() is None
