"""Public Model elements can target the existing validated Realization routes."""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, realize
from pyinto.constructs import ConstructError, Symbol
from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)
from tests.support.c_realizer import C_DECLARATIONS, c_bindings


def test_construct_and_variant_via_public_language_element() -> None:
    @realizes(lang.While)
    class CWhile:
        template = "while (${condition}) {\n${body}\n}"

    @realizes(lang.Branch)
    class CBranchWithElse:
        variant = "with_else"
        template = "if (${condition}) {${then}} else {${otherwise}}"

    registry = RealizationRegistry("c", (CWhile, CBranchWithElse))
    assert (
        registry.recipe(
            PythonFrontend().parse("while True:\n    break").body.children[0],
            EmitContext(registry),
        ).template
        == "while (${condition}) {\n${body}\n}"
    )
    assert (
        registry.recipe(
            PythonFrontend()
            .parse("if True:\n    pass\nelse:\n    pass")
            .body.children[0],
            EmitContext(registry),
        ).template
        is not None
    )


def test_builtin_direct_call_and_dedicated_construct_stay_distinct() -> None:
    @realizes(builtin.PrintCall)
    class PrintCall:
        accepts = ("string",)
        requires = ("stdio.h",)
        template = "puts(${arg0});"

    entries = tuple(e for e in C_DECLARATIONS if e.__name__ != "CPrint") + (PrintCall,)
    registry = RealizationRegistry("c", entries)
    source = 'print("hello")'
    assert 'puts("hello");' in realize(
        PythonFrontend().parse(source), realizations=registry
    )
    assert realize(PythonFrontend().parse(source), realizations=registry) == realize(
        PythonFrontend().parse(source), realizations=c_bindings()
    )

    # A separate PrintValues Construct is used for complex print operations.
    with pytest.raises(ConstructError, match="PrintValues"):
        realize(PythonFrontend().parse('print("a", "b")'), realizations=registry)

    @realizes(builtin.PrintValues)
    class PrintValues:
        supports = (
            "output.print.evaluate_before_write",
            "output.print.space_join_newline",
        )
        render = lambda node, ctx: "custom output"

    registry = RealizationRegistry("c", (PrintCall, PrintValues))
    assert (
        registry.recipe(
            PythonFrontend().parse('print("a", "b")').body.children[0],
            EmitContext(registry),
        ).selector
        is not None
    )


def test_model_valuekind_and_mappedtype_use_original_type_keys() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = "long long"

    @realizes(vt.String)
    class String:
        type_name = "const char *"

    external = vt.MappedType("example.external", "owned")

    @realizes(external)
    class External:
        type_name = lambda value, spell: "handle_t" if value == external else "bad"

    registry = RealizationRegistry("c", (Integer, String, External))
    assert (
        registry.type_name(Symbol("x", vt.ValueType(vt.Integer), "int")) == "long long"
    )
    assert (
        registry.type_name(Symbol("s", vt.ValueType(vt.String), "str"))
        == "const char *"
    )
    assert registry.type_name(Symbol("p", external, "External")) == "handle_t"


def test_same_public_element_cannot_be_registered_twice() -> None:
    @realizes(lang.While)
    class FirstConstruct:
        template = "while (${condition}) {${body}}"

    @realizes(lang.While)
    class SecondConstruct:
        template = "while (${condition}) {${body}}"

    with pytest.raises(ValueError, match="Duplicate .* realization"):
        RealizationRegistry("c", (FirstConstruct, SecondConstruct))

    @realizes(builtin.PrintCall)
    class FirstCall:
        template = "f(${arg0})"

    @realizes(builtin.PrintCall)
    class SecondCall:
        template = "f(${arg0})"

    with pytest.raises(ValueError, match="Duplicate call realization"):
        RealizationRegistry("c", (FirstCall, SecondCall))

    @realizes(vt.Integer)
    class FirstType:
        type_name = "long long"

    @realizes(vt.Integer)
    class SecondType:
        type_name = "long long"

    with pytest.raises(ValueError, match="Duplicate type spelling"):
        RealizationRegistry("c", (FirstType, SecondType))


@pytest.mark.parametrize(
    "invalid", ["print", "integer", None, object(), int, vt.ValueKind.MAPPED_OBJECT, 42]
)
def test_unknown_element_rejected_fail_closed(invalid: object) -> None:
    @realizes(invalid)
    class Invalid:
        template = "text"

    with pytest.raises(
        ValueError, match="published Construct, builtin Call, or Model type"
    ):
        RealizationRegistry("c", (Invalid,))


def test_one_role_only_and_existing_validation_are_preserved() -> None:
    class Unmarked:
        template = "ok"

    with pytest.raises(ValueError, match="exactly one role"):
        RealizationRegistry("c", (Unmarked,))

    @realizes(lang.While)
    class BadHole:
        template = "${unknown}"

    with pytest.raises(ValueError, match="unknown template hole"):
        RealizationRegistry("c", (BadHole,))

    @realizes(builtin.PrintCall)
    class BadCallHole:
        accepts = ("string",)
        template = "${arg1}"

    with pytest.raises(ValueError, match="Invalid call hole"):
        RealizationRegistry("c", (BadCallHole,))

    @realizes(lang.While)
    class BadContract:
        supports = ("not.a.valid-identifier",)
        template = "${body}"

    with pytest.raises(ValueError, match="unique namespaced"):
        RealizationRegistry("c", (BadContract,))

    @realizes(vt.Integer)
    class MissingTypeName:
        template = "no"

    with pytest.raises(ValueError, match="Type spelling requires"):
        RealizationRegistry("c", (MissingTypeName,))


def test_only_explicit_builtin_call_element_is_accepted() -> None:
    # A newly created lookalike is not the Host's published direct-call token.
    other = type(builtin.PrintCall)("print")

    @realizes(other)
    class Lookalike:
        template = "foo(${arg0})"

    with pytest.raises(ValueError, match="published Construct"):
        RealizationRegistry("c", (Lookalike,))
