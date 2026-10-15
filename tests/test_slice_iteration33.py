"""Iteration 33: source-ordered, omission-preserving typed sequence slices."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto.constructs import (
    ConstructError,
    FunctionCall,
    ListElement,
    ListType,
    Literal,
    Reference,
    SliceValue,
    StringElement,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION, required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes


def _value(source: str) -> object:
    program = PythonFrontend().parse(source)
    return program.body.children[-1].value  # type: ignore[attr-defined]


def test_list_slice_preserves_omitted_start_vs_explicit_zero() -> None:
    omitted = _value("xs: list[int] = [0, 1, 2]\ny: list[int] = xs[:2]")
    explicit = _value("xs: list[int] = [0, 1, 2]\ny: list[int] = xs[0:2]")
    assert isinstance(omitted, SliceValue)
    assert isinstance(explicit, SliceValue)
    assert omitted.start is None
    assert explicit.start == Literal(0)
    assert set(omitted.parts()) == {"source", "stop"}
    assert set(explicit.parts()) == {"source", "start", "stop"}
    assert omitted.stop == Literal(2)
    assert omitted.value_type == ValueType(
        ValueKind.LIST, list_type=ListType(ValueType(ValueKind.INTEGER))
    )
    assert omitted.variant() == "list"
    with pytest.raises(FrozenInstanceError):
        omitted.stop = Literal(3)  # type: ignore[misc]


def test_negative_step_keeps_omitted_bounds_distinct_from_explicit_zero() -> None:
    reversed_all = _value("result: str = 'abc'[::-1]")
    from_zero = _value("result: str = 'abc'[0::-1]")
    assert isinstance(reversed_all, SliceValue)
    assert isinstance(from_zero, SliceValue)
    assert reversed_all.start is None and reversed_all.stop is None
    assert reversed_all.step == Literal(-1)
    assert set(reversed_all.parts()) == {"source", "step"}
    assert from_zero.start == Literal(0)
    assert from_zero.value_type == ValueType(ValueKind.STRING)
    assert reversed_all.variant() == "string"


def test_full_slice_is_retained_and_not_an_identity_operation() -> None:
    result = _value("xs: list[str] = ['a', 'b']\ny: list[str] = xs[:]")
    assert isinstance(result, SliceValue)
    assert result.parts() == {"source": result.source}
    assert result.value_type == result.source.value_type
    assert required_contracts(result) == {
        "slice.evaluate_source_bounds_once_in_order",
        "slice.python_indices_and_zero_step",
        "slice.list.shallow_outer_copy",
    }


def test_zero_step_is_an_expression_with_runtime_failure_contract() -> None:
    result = _value("xs: list[int] = [1]\ny: list[int] = xs[::0]")
    assert isinstance(result, SliceValue)
    assert result.step == Literal(0)
    assert "step" in result.parts()
    assert "slice.python_indices_and_zero_step" in required_contracts(result)
    # Do not execute or fold the source expression at parse time.


def test_slice_bounds_remain_ordered_single_value_nodes() -> None:
    value = _value("""
def make() -> list[int]:
    return [1, 2, 3]

def lo() -> int:
    return 0

def hi() -> int:
    return 2

def stride() -> int:
    return 1

result: list[int] = make()[lo():hi():stride()]
""")
    assert isinstance(value, SliceValue)
    assert all(
        isinstance(getattr(value, field), FunctionCall)
        for field in ("source", "start", "stop", "step")
    )
    assert tuple(value.parts()) == ("source", "start", "stop", "step")
    assert value.source.signature.name == "make"  # type: ignore[attr-defined]
    assert value.start.signature.name == "lo"  # type: ignore[attr-defined]
    assert value.stop.signature.name == "hi"  # type: ignore[attr-defined]
    assert value.step.signature.name == "stride"  # type: ignore[attr-defined]


def test_list_slice_can_be_followed_by_index_or_slice_again() -> None:
    index = _value("xs: list[int] = [1, 2, 3]\ny: int = xs[1:][0]")
    chained = _value("xs: list[int] = [1, 2, 3]\ny: list[int] = xs[1:][::-1]")
    assert isinstance(index, ListElement)
    assert isinstance(index.source, SliceValue)
    assert isinstance(chained, SliceValue)
    assert isinstance(chained.source, SliceValue)


def test_string_slice_can_be_indexed_using_existing_string_element() -> None:
    index = _value("c: str = 'abc'[1:][0]")
    assert isinstance(index, StringElement)
    assert isinstance(index.source, SliceValue)


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("n: int = 4\nx: int = n[1:2]", "Slicing requires a typed list or string"),
        (
            "t: tuple[int, int] = (1, 2)\nx: tuple[int, int] = t[:1]",
            "Slicing requires a typed list or string",
        ),
        (
            "d: dict[int, int] = {1: 2}\nx: dict[int, int] = d[:1]",
            "Slicing requires a typed list or string",
        ),
        (
            "xs: list[int] = [1]\ny: list[int] = xs[True:]",
            "Slice start requires an integer Value",
        ),
        (
            "xs: list[int] = [1]\ny: list[int] = xs[:1.0]",
            "Slice stop requires an integer Value",
        ),
        ("s: str = 'abc'\nt: str = s[::'a']", "Slice step requires an integer Value"),
        ("xs: list[int] = [1]\ny: list[int] = xs[:missing]", "Unresolved name"),
    ],
)
def test_frontend_rejects_unsupported_slicing(source: str, error: str) -> None:
    with pytest.raises(UnsupportedPython, match=error):
        PythonFrontend().parse(source)


def test_model_rejects_bad_source_and_bound_without_frontend() -> None:
    with pytest.raises(ConstructError, match="typed list or string"):
        SliceValue(Literal(42))
    with pytest.raises(ConstructError, match="Slice start requires"):
        SliceValue(Literal("abc"), Literal("bad"))
    with pytest.raises(ConstructError, match="Slice step requires"):
        SliceValue(Literal("abc"), step=Literal("bad"))
    with pytest.raises(ConstructError, match="Slice stop requires"):
        SliceValue(Literal("abc"), stop="bad")  # type: ignore[arg-type]


def test_contracts_differ_by_source_type_without_target_inference() -> None:
    left = _value("xs: list[int] = [1]\ny: list[int] = xs[:]")
    right = _value("s: str = 'abc'\ny: str = s[:]")
    assert isinstance(left, SliceValue)
    assert isinstance(right, SliceValue)
    assert "slice.list.shallow_outer_copy" in required_contracts(left)
    assert "slice.string.unicode_codepoints" in required_contracts(right)
    assert "slice.list.shallow_outer_copy" not in required_contracts(right)
    assert isinstance(right.source, Reference)
    assert any(
        declaration.construct is SliceValue
        for declaration in LANGUAGE_ADMISSION.declarations
    )


def test_slice_realization_missing_obligation_is_rejected() -> None:
    left = _value("xs: list[int] = [1]\ny: list[int] = xs[:]")
    assert isinstance(left, SliceValue)

    @realizes(SliceValue)
    class Incomplete:
        variant = "list"
        template = "${source}"
        supports = (
            "slice.evaluate_source_bounds_once_in_order",
            "slice.python_indices_and_zero_step",
        )

    reg = RealizationRegistry("probe", (Incomplete,))
    with pytest.raises(ConstructError, match="slice.list.shallow_outer_copy"):
        reg.recipe(left, EmitContext(reg))

    @realizes(SliceValue)
    class Declared:
        variant = "list"
        template = "${source}"
        supports = (
            "slice.evaluate_source_bounds_once_in_order",
            "slice.python_indices_and_zero_step",
            "slice.list.shallow_outer_copy",
        )

    reg = RealizationRegistry("probe", (Declared,))
    assert reg.recipe(left, EmitContext(reg)).template == "${source}"
    # Support declarations do not prove that ${source} implements a shallow copy.


def test_existing_single_element_index_does_not_change() -> None:
    result = _value("xs: list[int] = [1, 2]\nx: int = xs[0]")
    assert isinstance(result, ListElement)
    assert not isinstance(result, SliceValue)
