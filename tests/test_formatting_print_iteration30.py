"""Iteration 30: Model-first string formatting and typed output contracts."""

from __future__ import annotations

import ast

import pytest

from pyinto import PythonFrontend, realize
from pyinto.constructs import (
    Call,
    ConstructError,
    FormattedString,
    Initialize,
    IntrinsicCall,
    Literal,
    PrintValues,
    ValueKind,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION, required_contracts
from pyinto.frontend import UnsupportedPython
from pyinto.frontend.expressions import ExpressionNormalizer
from pyinto.intrinsics import IntrinsicRegistry, standard_intrinsics
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.python_realizer.pack import python_bindings


def _last(source: str):
    return PythonFrontend().parse(source).body.children[-1]


def test_format_parts_have_typed_str_signatures_and_source_order() -> None:
    node = _last('n: int = 7\nf: float = 1.0\ntext: str = f"n={n}; f={f}"')
    assert isinstance(node, Initialize)
    formatted = node.value
    assert isinstance(formatted, FormattedString)
    assert formatted.kind is ValueKind.STRING
    assert formatted.fragments[0] == Literal("n=")
    assert formatted.fragments[2] == Literal("; f=")
    assert isinstance(formatted.fragments[1], IntrinsicCall)
    assert isinstance(formatted.fragments[3], IntrinsicCall)
    assert formatted.fragments[1].definition.obligations == {
        "intrinsic.stringify.int_repr"
    }
    assert formatted.fragments[3].definition.obligations == {
        "intrinsic.stringify.float_repr"
    }
    assert formatted.parts()["fragments"] == formatted.fragments
    assert required_contracts(formatted) == {"format.string.fragments_once_in_order"}
    assert "intrinsic.stringify.float_repr" in required_contracts(
        formatted.fragments[3]
    )


@pytest.mark.parametrize(
    "source",
    [
        's: str = f""',
        's: str = f"hello"',
        's: str = f"{True!s}"',
        's: str = f"{123}"',
        's: str = f"{{x}}={3}"',
    ],
)
def test_supported_format_sources(source: str) -> None:
    result = _last(source)
    assert isinstance(result, Initialize)
    assert isinstance(result.value, FormattedString)
    assert result.value.kind is ValueKind.STRING


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('s: str = f"{2!r}"', "format spec"),
        ('s: str = f"{2!a}"', "format spec"),
        ('s: str = f"{2:04d}"', "format spec"),
        ('s: str = f"{2.5:.2f}"', "format spec"),
        ('xs: list[int] = [1]\ns: str = f"{xs}"', "No typed str conversion"),
        ('s: str = f"{None}"', "No typed str conversion"),
        ('print(1, sep=";")', "positional arguments"),
        ('print(*["a"])', "positional arguments"),
        ("print(object())", "Unregistered interface mapping call"),
    ],
)
def test_unsupported_formatting_is_rejected(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend().parse(source)


def test_provider_must_register_stringification() -> None:
    with pytest.raises(UnsupportedPython, match="No typed str conversion"):
        PythonFrontend(intrinsics=IntrinsicRegistry()).parse('s: str = f"{1}"')
    assert PythonFrontend(intrinsics=standard_intrinsics()).parse('s: str = f"{1}"')


@pytest.mark.parametrize(
    ("source", "count"),
    [
        ("print()", 0),
        ("print(1)", 1),
        ('print(1, 1.0, True, "hi")', 4),
        ('print("hi", 1)', 2),
    ],
)
def test_extended_print_uses_typed_conversion(source: str, count: int) -> None:
    node = _last(source)
    assert isinstance(node, PrintValues)
    assert len(node.values) == count
    assert all(isinstance(value, IntrinsicCall) for value in node.values)
    assert all(value.value_type.kind is ValueKind.STRING for value in node.values)
    assert all(value.definition.key == "intrinsic.global.str" for value in node.values)
    assert required_contracts(node) == {
        "output.print.space_join_newline",
        "output.print.evaluate_before_write",
    }


def test_single_string_print_retains_existing_pack_behavior() -> None:
    node = _last('print("hello")')
    assert isinstance(node, Call)
    assert "print('hello')" in realize(
        PythonFrontend().parse('print("hello")'), realizations=python_bindings()
    )


def test_new_print_or_format_does_not_silently_use_old_pack_recipes() -> None:
    with pytest.raises(ConstructError, match="No .* realization"):
        realize(PythonFrontend().parse("print(1, 2)"), realizations=python_bindings())
    with pytest.raises(ConstructError, match="No .* realization"):
        realize(
            PythonFrontend().parse('s: str = f"{3}"'), realizations=python_bindings()
        )


def test_admission_requirements_are_enforced_before_rendering() -> None:
    formatted = _last('s: str = f"hi"')
    assert isinstance(formatted, Initialize)

    @realizes(FormattedString)
    class StringOnly:
        template = "${fragments}"

    bindings = RealizationRegistry("test", (StringOnly,))
    with pytest.raises(ConstructError, match="format.string.fragments_once_in_order"):
        bindings.recipe(formatted.value, EmitContext(bindings))

    @realizes(FormattedString)
    class StringOrdered:
        template = "${fragments}"
        supports = ("format.string.fragments_once_in_order",)

    bindings = RealizationRegistry("test", (StringOrdered,))
    assert bindings.recipe(formatted.value, EmitContext(bindings)).template

    printed = _last("print()")
    assert isinstance(printed, PrintValues)

    @realizes(PrintValues)
    class PrintOnly:
        template = 'puts("")'
        supports = ("output.print.space_join_newline",)

    bindings = RealizationRegistry("test", (PrintOnly,))
    with pytest.raises(ConstructError, match="output.print.evaluate_before_write"):
        bindings.recipe(printed, EmitContext(bindings))
    assert any(
        item.construct is PrintValues for item in LANGUAGE_ADMISSION.declarations
    )


def test_model_rejects_nonstrings_and_empty_format_segments() -> None:
    with pytest.raises(ConstructError, match="string Value fragments"):
        FormattedString(())
    with pytest.raises(ConstructError, match="string Value fragments"):
        FormattedString((Literal(2),))
    with pytest.raises(ConstructError, match="string Value arguments"):
        PrintValues((Literal(2),))


def test_source_expressions_are_normalized_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ExpressionNormalizer._value
    seen: list[ast.Call] = []

    def spy(self, node, expected=None):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "get"
        ):
            seen.append(node)
        return original(self, node, expected)

    monkeypatch.setattr(ExpressionNormalizer, "_value", spy)
    PythonFrontend().parse(
        'def get() -> int:\n    return 4\ns: str = f"{get()}"\nprint(get(), get())'
    )
    assert len(seen) == 3
