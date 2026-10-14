"""Naming policy is a distinct, exclusive declaration kind."""

from __future__ import annotations

import pytest

from pyinto.constructs import ConstructError
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    forbidden_prefixes,
    naming,
    pack_entries,
    pack_target,
    realizes,
    requirement_line,
    reserved,
    supports,
    template,
)


def test_marker_preserves_all_naming_policy_information() -> None:
    @naming
    class CNames:
        reserved @= frozenset({"while", "auto"})
        forbidden_prefixes @= ("__", "pyinto_")
        requirement_line @= "#include <${name}>"

    registry = RealizationRegistry("c", (CNames,))
    assert registry.name("local") == "local"
    for rejected in ("while", "auto", "__hidden", "pyinto_private"):
        with pytest.raises(ConstructError, match="not portable"):
            registry.name(rejected)
    ctx = EmitContext(registry)
    ctx.headers.update(("stdio.h", "math.h"))
    assert registry.requirements(ctx) == "#include <math.h>\n#include <stdio.h>"


def test_separate_naming_definitions_with_equal_rules_behave_the_same() -> None:
    @naming
    class First:
        reserved @= frozenset({"switch"})
        forbidden_prefixes @= ("__",)
        requirement_line @= '#include "${name}"'

    @naming
    class Second:
        reserved @= frozenset({"switch"})
        forbidden_prefixes @= ("__",)
        requirement_line @= '#include "${name}"'

    first = RealizationRegistry("c", (First,))
    second = RealizationRegistry("c", (Second,))
    for registry in (first, second):
        with pytest.raises(ConstructError, match="not portable"):
            registry.name("switch")
        with pytest.raises(ConstructError, match="not portable"):
            registry.name("__secret")
    ctx_first, ctx_second = EmitContext(first), EmitContext(second)
    ctx_first.headers.add("stdio.h")
    ctx_second.headers.add("stdio.h")
    assert first.requirements(ctx_first) == second.requirements(ctx_second)


def test_naming_default_policy_can_be_registered_from_pack() -> None:
    @naming
    class DefaultNaming:
        pass

    class CTargetPack:
        pack_target @= "c"
        pack_entries @= (DefaultNaming,)

    registry = RealizationRegistry.from_pack(CTargetPack)
    assert registry.name("regular_name") == "regular_name"


@pytest.mark.parametrize("reverse", (False, True))
def test_naming_and_realizes_are_mutually_exclusive(reverse: bool) -> None:
    if reverse:

        @naming
        @realizes(lang.While)
        class Invalid:
            template @= "while (${condition}) {${body}}"

    else:

        @realizes(lang.While)
        @naming
        class Invalid:
            template @= "while (${condition}) {${body}}"

    with pytest.raises(ValueError, match="exactly one role"):
        RealizationRegistry("c", (Invalid,))


def test_two_distinct_naming_definitions_are_rejected() -> None:
    @naming
    class First:
        pass

    @naming
    class Second:
        pass

    with pytest.raises(ValueError, match="Duplicate naming entry"):
        RealizationRegistry("c", (First, Second))
    with pytest.raises(ValueError, match="Duplicate naming entry"):
        RealizationRegistry("c", (First, First))


def test_naming_requirement_slot_stays_restricted() -> None:
    @naming
    class Invalid:
        requirement_line @= "#include <${unknown}>"

    with pytest.raises(ValueError, match="Requirement line only accepts"):
        RealizationRegistry("c", (Invalid,))


def test_naming_cannot_claim_construct_contracts() -> None:
    @naming
    class Invalid:
        supports @= ("call.arguments.bound",)

    with pytest.raises(ValueError, match="supports belongs"):
        RealizationRegistry("c", (Invalid,))


def test_naming_cannot_be_used_without_explicit_role() -> None:
    class Undeclared:
        reserved @= frozenset({"switch"})

    with pytest.raises(ValueError, match="exactly one role"):
        RealizationRegistry("c", (Undeclared,))
