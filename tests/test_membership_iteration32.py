"""Iteration 32: source-ordered, typed membership without Target recipes."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    ConstructError,
    DictValue,
    FunctionCall,
    ListValue,
    Literal,
    Membership,
    Reference,
    StringContains,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION, required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes, supports, template, variant


def _value(source: str) -> object:
    result = PythonFrontend().parse(source)
    return result.body.children[-1].value  # type: ignore[attr-defined]


def test_list_membership_retains_values_order_and_boolean_type() -> None:
    value = _value("xs: list[int] = [1, 2]\nx: int = 1\nfound: bool = x in xs")
    assert isinstance(value, Membership)
    assert isinstance(value.element, Reference)
    assert isinstance(value.container, Reference)
    assert value.parts() == {"element": value.element, "container": value.container}
    assert value.value_type == ValueType(ValueKind.BOOLEAN)
    assert value.variant() == "list_in"
    with pytest.raises(FrozenInstanceError):
        value.negate = True  # type: ignore[misc]


def test_list_not_in_and_expression_sources_preserve_order() -> None:
    value = _value("found: bool = 2 not in [1, 3]")
    assert isinstance(value, Membership)
    assert value.negate
    assert value.variant() == "list_not_in"
    assert value.element == Literal(2)
    assert isinstance(value.container, ListValue)


def test_dict_membership_is_key_membership_not_value_membership() -> None:
    value = _value('d: dict[str, int] = {"k": 5}\nfound: bool = "k" in d')
    assert isinstance(value, Membership)
    assert value.variant() == "dict_in"
    assert isinstance(value.container, Reference)
    literal = _value('found: bool = 3 not in {1: "a", 3: "b"}')
    assert isinstance(literal, Membership)
    assert isinstance(literal.container, DictValue)
    assert literal.variant() == "dict_not_in"
    assert required_contracts(literal) == {
        "membership.operands.left_to_right",
        "membership.dict.key_hash_equality",
        "membership.negated",
    }


def test_existing_string_substring_model_is_retained() -> None:
    assert isinstance(_value('found: bool = "a" in "cat"'), StringContains)
    negative = _value('found: bool = "a" not in "cat"')
    assert isinstance(negative, StringContains)
    assert required_contracts(negative) == {
        "evaluation.operands.left_to_right",
        "membership.string.unicode_substring",
        "membership.negated",
    }


def test_membership_can_retain_callable_element_and_container_without_evaluation() -> (
    None
):
    parsed = _value("""
def item() -> int:
    return 1

def values() -> list[int]:
    return [1, 2]

found: bool = item() in values()
""")
    assert isinstance(parsed, Membership)
    assert isinstance(parsed.element, FunctionCall)
    assert isinstance(parsed.container, FunctionCall)
    assert parsed.element.signature.name == "item"
    assert parsed.container.signature.name == "values"


@pytest.mark.parametrize(
    ("source", "error"),
    [
        (
            'xs: list[int] = [1]\nfound: bool = "1" in xs',
            "List membership element type mismatch",
        ),
        (
            'd: dict[str, int] = {"a": 1}\nfound: bool = 1 in d',
            "Dict membership key type mismatch",
        ),
        ("found: bool = 1 in 2", "Membership requires a typed list or dict"),
        ("found: bool = 1 in (1, 2)", "Membership requires a typed list or dict"),
        ('found: bool = 1 in "abc"', "String membership requires"),
        ("found: bool = 1 < 2 in [1, 2]", "Unsupported chained comparison operator"),
        (
            "found: bool = 1 in [1, 2] in [[1], [2]]",
            "Unsupported chained comparison operator",
        ),
    ],
)
def test_rejects_unsupported_or_mismatched_membership(source: str, error: str) -> None:
    with pytest.raises(UnsupportedPython, match=error):
        PythonFrontend().parse(source)


def test_model_rejects_invalid_inputs_without_frontend() -> None:
    list_value = ListValue((Literal(1),), ValueType(ValueKind.INTEGER))
    with pytest.raises(ConstructError, match="element type mismatch"):
        Membership(Literal("1"), list_value)
    with pytest.raises(ConstructError, match="typed list or dict"):
        Membership(Literal(1), Literal(2))
    with pytest.raises(ConstructError, match="negation must be Boolean"):
        Membership(Literal(1), list_value, 1)  # type: ignore[arg-type]
    with pytest.raises(ConstructError, match="operands must be Values"):
        Membership("1", list_value)  # type: ignore[arg-type]


def test_provider_admission_checks_required_contracts_before_render() -> None:
    value = _value("found: bool = 1 in [1, 2]")
    assert isinstance(value, Membership)
    assert any(decl.construct is Membership for decl in LANGUAGE_ADMISSION.declarations)
    assert required_contracts(value) == {
        "membership.operands.left_to_right",
        "membership.list.identity_or_equality",
    }

    @realizes(Membership)
    class Insufficient:
        variant @= "list_in"
        template @= "${element}"
        supports @= ("membership.list.identity_or_equality",)

    registry = RealizationRegistry("probe", (Insufficient,))
    with pytest.raises(ConstructError, match="membership.operands.left_to_right"):
        registry.recipe(value, EmitContext(registry))

    @realizes(Membership)
    class Declared:
        variant @= "list_in"
        template @= "${element}"
        supports @= (
            "membership.list.identity_or_equality",
            "membership.operands.left_to_right",
        )

    registry = RealizationRegistry("probe", (Declared,))
    assert registry.recipe(value, EmitContext(registry)).template == "${element}"
    # supports only attests to a declaration, not the correctness of this template.


def test_negated_membership_requires_independent_contract() -> None:
    value = _value("found: bool = 1 not in [1, 2]")
    assert isinstance(value, Membership)
    assert "membership.negated" in required_contracts(value)


def test_different_element_types_preserve_exact_typed_matching() -> None:
    for source, variant_name in (
        ('v: str = "a"\nxs: list[str] = ["a"]\nb: bool = v in xs', "list_in"),
        ("v: float = 1.5\nxs: list[float] = [1.5]\nb: bool = v in xs", "list_in"),
        ("v: bool = True\nxs: list[bool] = [True]\nb: bool = v in xs", "list_in"),
        ('d: dict[int, str] = {2: "ok"}\nb: bool = 2 in d', "dict_in"),
    ):
        result = _value(source)
        assert isinstance(result, Membership)
        assert result.variant() == variant_name
