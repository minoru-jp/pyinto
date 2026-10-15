"""SDD phase 6: Model part contracts and construction-time validation."""

from __future__ import annotations

import pytest

from pyinto.admission import AdmissionDeclaration
from pyinto.constructs import (
    Assign,
    Block,
    Branch,
    Comparison,
    Construct,
    ConstructError,
    ContextEntry,
    Initialize,
    Literal,
    Program,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
    While,
    With,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from pyinto.realizations.registry import Composer, RealizationRegistry
from pyinto.realizations.regulation import realizes


def _number(name: str = "n") -> Symbol:
    return Symbol(name, ValueType(ValueKind.INTEGER), "int")


def _boolean(name: str = "flag") -> Symbol:
    return Symbol(name, ValueType(ValueKind.BOOLEAN), "bool")


@pytest.mark.parametrize(
    "create, message",
    [
        (lambda: Comparison(Literal(1), "+", Literal(2)), "Unsupported comparison"),
        (lambda: Comparison(Literal("x"), "==", Literal(2)), "requires integers"),
        (
            lambda: Initialize(_number(), Literal("wrong")),
            "Initialization type mismatch",
        ),
        (
            lambda: Assign(Reference(_number()), Literal("wrong")),
            "Assignment type mismatch",
        ),
        (lambda: Branch(Literal(1), Block(())), "Branch condition must be Boolean"),
        (lambda: While(Literal(1), Block(())), "While condition must be Boolean"),
    ],
)
def test_cst_014_invalid_model_rejected_at_construction(
    create: object, message: str
) -> None:
    assert callable(create)
    with pytest.raises(ConstructError, match=message):
        create()  # type: ignore[operator]


def test_cst_014_valid_parts_remain_structural() -> None:
    number = _number()
    condition = Comparison(Reference(number), "<", Literal(3))
    branch = Branch(Reference(_boolean()), Block(()), Block(()))
    loop = While(Reference(_boolean()), Block((branch,)))
    assignment = Assign(Reference(number), Literal(1))
    initialize = Initialize(number, Literal(0))
    assert condition.parts()["op"] == "<"
    assert branch.parts()["otherwise"] is branch.else_body
    assert loop.parts()["body"].children == (branch,)
    assert assignment.parts()["target"] == Reference(number)
    assert initialize.parts()["value"] == Literal(0)


def test_cst_013_possible_names_are_not_mandatory_slots() -> None:
    assert Branch.accepts_part_name("otherwise")
    assert "otherwise" not in Branch(Reference(_boolean()), Block(())).parts()
    assert Program.accepts_part_name("body")
    assert not Program.accepts_part_name("requirements")
    assert With.accepts_part_name("entry0")
    assert With.accepts_part_name("entry15")
    assert not With.accepts_part_name("entry01")
    assert not With.accepts_part_name("entry-1")
    assert not With.accepts_part_name("name")


def test_cmp_012_static_with_entry_is_accepted_and_composed() -> None:
    @realizes(With)
    class WithRule:
        supports = ("context.with.enter_exit_exception",)
        template = "${entry0} / ${body}"

    @realizes(ContextEntry)
    class EntryRule:
        template = "${context}"

    @realizes(Block)
    class BlockRule:
        template = "${children}"

    @realizes(Literal)
    class LiteralRule:
        variant = "integer"
        template = "one"

    composer = Composer(
        RealizationRegistry("test", (WithRule, EntryRule, BlockRule, LiteralRule))
    )
    one = With((ContextEntry(Literal(1)),), Block(()))
    assert composer.source(one) == "one / \n"


def test_cmp_012_missing_dynamic_part_is_rejected_at_composition() -> None:
    @realizes(With)
    class WithRule:
        supports = ("context.with.enter_exit_exception",)
        template = "${entry1}"

    registry = RealizationRegistry("test", (WithRule,))
    with pytest.raises(ConstructError, match="Unfilled template holes"):
        Composer(registry).source(With((ContextEntry(Literal(1)),), Block(())))


def test_cmp_012_unknown_model_part_rejected_at_pack_validation() -> None:
    @realizes(With)
    class BadWithRule:
        template = "${entry_unknown}"

    with pytest.raises(ValueError, match="unknown template hole"):
        RealizationRegistry("test", (BadWithRule,))


def test_cst_013_existing_custom_construct_holes_remain_supported() -> None:
    class Custom(Construct):
        HOLES = frozenset({"value"})

        def parts(self) -> dict[str, object]:
            return {"value": Literal(1)}

    @realizes(Custom)
    class CustomRule:
        template = "${value}"

    @realizes(Literal)
    class LiteralRule:
        variant = "integer"
        template = "1"

    assert (
        Composer(
            RealizationRegistry("test", (CustomRule, LiteralRule)),
            admission=LANGUAGE_ADMISSION.extend((AdmissionDeclaration(Custom),)),
        ).source(Custom())
        == "1\n"
    )
