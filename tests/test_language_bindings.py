"""Shikumi validation and late composition without four-phase snippets."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from shikumi_contrace import binds as contract_binds
from shikumi_contrace import upholds

from pyinto import ConstructError, PythonFrontend, realize
from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import (
    Block,
    Branch,
    Construct,
    Literal,
    Program,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
    While,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.contracts.construct_contract import ConstructContract
from pyinto.contracts.ports.pipeline import CompositionPort
from pyinto.interfaces import builtins as builtin
from pyinto.realizations import Composer, RealizationRegistry
from pyinto.realizations.layout import Template, Text
from pyinto.realizations.layout import render as render_layout
from pyinto.realizations.regulation import (
    pack_entries,
    pack_target,
    realizes,
    render,
    template,
    variant,
)
from tests.support.c_realizer import C_DECLARATIONS, CTargetPack, c_bindings


@contract_binds[CompositionPort](Composer)
@upholds(ConstructContract.LateComposition)
def test_nested_layout_is_not_flattened_before_rendering() -> None:
    program = PythonFrontend().parse('n: int = 1\nif n > 0:\n    print("ok")')
    composer = Composer(c_bindings())
    tree = composer.layout(program)
    assert isinstance(tree, Template)
    assert isinstance(tree.slots["body"], Template)
    block = tree.slots["body"]
    assert isinstance(block, Template)
    assert not isinstance(block.slots["children"], str)
    assert render_layout(tree, composer.context).endswith("}")
    assert 'puts("ok")' in render_layout(tree, composer.context)


@contract_binds[CompositionPort](Composer)
@upholds(ConstructContract.BindingValidation)
def test_unknown_hole_fails_pack_validation() -> None:
    @realizes(Branch)
    class BadBranch:
        template @= "if (${mystery}) {}"

    with pytest.raises(ValueError, match="unknown template hole"):
        RealizationRegistry("c", (BadBranch,))


@contract_binds[CompositionPort](Composer)
@upholds(ConstructContract.BindingValidation)
def test_pack_validates_duplicate_and_ambiguous_recipes() -> None:
    class Empty:
        template @= "text"

    with pytest.raises(ValueError, match="exactly one role"):
        RealizationRegistry("c", (Empty,))
    with pytest.raises(ValueError, match="Duplicate c realization"):
        RealizationRegistry("c", (C_DECLARATIONS[0], C_DECLARATIONS[0]))

    @realizes(Branch)
    class Bad:
        template @= "ok"
        render @= lambda node, ctx: "extra"

    with pytest.raises(ValueError, match="exactly one template or renderer"):
        RealizationRegistry("c", (Bad,))


@contract_binds[CompositionPort](Composer)
@upholds(ConstructContract.TargetIsolation)
def test_replace_pack_without_touching_normalization() -> None:
    @realizes(Literal)
    class AlternateStringLiteral:
        variant @= "string"
        render @= lambda node, context: Text('"other"')

    entries = tuple(x for x in C_DECLARATIONS if x.__name__ != "CStringLiteral") + (
        AlternateStringLiteral,
    )

    class Target:
        pack_target @= "c"
        pack_entries @= entries

    program = PythonFrontend().parse('print("original")')
    assert 'puts("original");' in realize(program, realizations=c_bindings())
    assert 'puts("other");' in realize(
        program, realizations=RealizationRegistry.from_pack(Target)
    )


def test_invalid_pack_and_call_slots_fail() -> None:
    class Missing:
        pack_target @= "c"

    with pytest.raises(ValueError, match="Pack missing entries"):
        RealizationRegistry.from_pack(Missing)

    @realizes(builtin.PrintCall)
    class BadCall:
        template @= "some(${unknown})"

    with pytest.raises(ValueError, match="Invalid call hole"):
        RealizationRegistry("c", (BadCall,))
    assert RealizationRegistry.from_pack(CTargetPack).target == "c"


def test_missing_recipe_and_explicit_pack_selection() -> None:
    program = PythonFrontend().parse('print("hello")')
    with pytest.raises(ConstructError, match="No 'c' realization"):
        realize(program, realizations=RealizationRegistry("c", ()))
    assert 'puts("hello")' in realize(program, realizations=c_bindings())


def test_missing_variant_rejected_even_if_default_is_registered() -> None:
    p = PythonFrontend().parse(
        'n: int = 0\nif n > 0:\n    print("x")\nelse:\n    print("y")'
    )
    entries = tuple(x for x in C_DECLARATIONS if x.__name__ != "CBranchWithElse")
    with pytest.raises(ConstructError, match="Branch:with_else"):
        realize(p, realizations=RealizationRegistry("c", entries))


def test_while_else_requires_an_explicit_binding_variant() -> None:
    p = PythonFrontend().parse(
        'n: int = 0\nwhile n < 1:\n    n = 1\nelse:\n    print("done")'
    )
    entries = tuple(x for x in C_DECLARATIONS if x.__name__ != "CWhileWithElse")
    with pytest.raises(ConstructError, match="While:with_else"):
        realize(p, realizations=RealizationRegistry("c", entries))


def test_while_uses_shikumi_slot_validation() -> None:
    @realizes(While)
    class BadWhile:
        template @= "while (${not_a_condition}) { ${body} }"

    with pytest.raises(ValueError, match="unknown template hole"):
        RealizationRegistry("c", (BadWhile,))


def test_manual_while_rejects_non_boolean_entry() -> None:
    with pytest.raises(ConstructError, match="While condition must be Boolean"):
        While(Literal(1), Block(()))


def test_selector_is_pure_template_choice_not_output() -> None:
    @dataclass(frozen=True)
    class Outer(Construct):
        child: Construct
        HOLES = frozenset({"inner"})

        def parts(self) -> dict[str, object]:
            return {"inner": self.child}

    @realizes(Outer)
    class OuterBinding:
        render @= lambda node, ctx: "/*start*/\n${inner}\n/*end*/"

    pack = RealizationRegistry("c", (*C_DECLARATIONS, OuterBinding))
    program = Program(
        Block((Outer(PythonFrontend().parse('print("ok")').body.children[0]),))
    )
    code = realize(
        program,
        realizations=pack,
        admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(Outer),)),
    )
    assert "/*start*/" in code and "/*end*/" in code
    assert 'puts("ok");' in code


def test_callback_must_produce_a_template_string() -> None:
    class Node(Construct):
        pass

    @realizes(Node)
    class Invalid:
        render @= lambda node, ctx: 123

    registry = RealizationRegistry("c", (*C_DECLARATIONS, Invalid))
    with pytest.raises(ConstructError, match="template text"):
        realize(
            Program(Block((Node(),))),
            realizations=registry,
            admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(Node),)),
        )


def test_unexpected_inline_multiline_slot_is_rejected() -> None:
    tree = Template("prefix ${value}", {"value": Text("a\nb")})
    composer = Composer(c_bindings())
    with pytest.raises(ConstructError, match="Multiline Slot"):
        render_layout(tree, composer.context)


def test_missing_slot_rejected() -> None:
    with pytest.raises(ConstructError, match="Unfilled template holes"):
        Template("hi ${missing}", {})


def test_composition_indents_nested_blocks_and_is_deterministic() -> None:
    p = PythonFrontend().parse(
        'n: int = 1\nif n > 0:\n    if n > 0:\n        print("nested")'
    )
    text = realize(p, realizations=c_bindings())
    assert '        if ((n > 0LL)) {\n            puts("nested");' in text
    assert text == realize(p, realizations=c_bindings())


def test_binding_for_derived_node_requires_explicit_registration() -> None:
    class Derived(Program):
        pass

    p = Derived(PythonFrontend().parse('print("x")').body)
    with pytest.raises(
        ConstructError, match="Unregistered Construct admission: Derived"
    ):
        realize(p, realizations=c_bindings())


def test_literal_template_marker_is_never_interpreted_as_a_slot(tmp_path) -> None:
    from tests.test_construct_pipeline import run_c

    program = PythonFrontend().parse('print("literal ${body} ${name}")')
    source = realize(program, realizations=c_bindings())
    assert "${body} ${name}" in source
    assert run_c(source, tmp_path).stdout == b"literal ${body} ${name}\n"

    python_source = realize(
        program,
        realizations=__import__(
            "tests.support.python_realizer.pack", fromlist=["python_bindings"]
        ).python_bindings(),
    )
    assert "${body} ${name}" in python_source


def test_leaf_literal_binding_may_not_silently_discard_children() -> None:
    @realizes(Branch)
    class BadBranch:
        render @= lambda node, context: Text("not a branch")

    registry = RealizationRegistry(
        "c",
        (
            *tuple(
                entry
                for entry in C_DECLARATIONS
                if entry.__name__ == "CProgram"
                or entry.__name__ == "CBlock"
                or entry.__name__ == "CIntegerLiteral"
            ),
            BadBranch,
        ),
    )
    # A populated construct cannot be treated as an opaque Text fragment.
    with pytest.raises(ConstructError, match="only realize leaf"):
        Composer(registry).layout(
            Branch(
                Reference(Symbol("n", ValueType(ValueKind.BOOLEAN), "bool")), Block(())
            )
        )
