"""A Python interface can declare static varargs and multiple call signatures."""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import Literal, ValueKind
from pyinto.interface_mapping import (
    InterfaceFunctionMapping,
    InterfaceMappingRegistry,
    InterfaceParameter,
    InterfaceVariadicParameter,
)

PREFIX = "from vendor.ops import compute\nr: int = "


def parse(registry: InterfaceMappingRegistry, call: str):
    return PythonFrontend(registry).parse(PREFIX + call)


def static_varargs() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                parameters=(InterfaceParameter("first", ValueKind.INTEGER),),
                variadic=InterfaceVariadicParameter("rest", ValueKind.INTEGER),
                factory=lambda args: Literal(sum(x.value for x in args)),
            ),
        )
    )


@pytest.mark.parametrize(
    "call,expected",
    [
        ("compute(1)", 1),
        ("compute(1, 2)", 3),
        ("compute(1, 2, 3)", 6),
        ("compute(first=7)", 7),
        ("compute(1, 2, 3, _force=True)", 6),
    ],
)
def test_static_varargs_normalize_flat_ordered_model(call, expected):
    assert parse(static_varargs(), call)
    captured: list[tuple] = []
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                parameters=(InterfaceParameter("first", ValueKind.INTEGER),),
                variadic=InterfaceVariadicParameter("rest", ValueKind.INTEGER),
                factory=lambda values: (captured.append(values), Literal(expected))[1],
            ),
        )
    )
    parse(registry, call)
    assert (
        tuple(x.value for x in captured[0])
        == (
            {
                "compute(1)": (1,),
                "compute(1, 2)": (1, 2),
                "compute(1, 2, 3)": (1, 2, 3),
                "compute(first=7)": (7,),
                "compute(1, 2, 3, _force=True)": (1, 2, 3),
            }[call]
        )
    )


def test_static_varargs_accepts_old_positional_signature_shape():
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.INTEGER,),
                lambda args: Literal(len(args)),
                variadic=InterfaceVariadicParameter("rest", ValueKind.INTEGER),
            ),
        )
    )
    parse(registry, "compute(1, 2, 3)")


@pytest.mark.parametrize(
    "call,error",
    [
        ("compute()", "Missing required"),
        ("compute(1, 'bad')", "variadic argument kind mismatch"),
        ("compute(1, rest=2)", "Unknown"),
        ("compute(1, first=2)", "Duplicate"),
        ("compute(1, *[2, 3])", "Expanded"),
        ("compute(1, **{'first': 2})", "Expanded"),
    ],
)
def test_varargs_rejects_unsafe_calls(call, error):
    with pytest.raises(UnsupportedPython, match=error):
        parse(static_varargs(), call)


def test_varargs_default_and_keyword_can_coexist_without_reordering_effects():
    found = []
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                parameters=(
                    InterfaceParameter("first", ValueKind.INTEGER),
                    InterfaceParameter("base", ValueKind.INTEGER, Literal(10)),
                ),
                variadic=InterfaceVariadicParameter("more", ValueKind.INTEGER),
                factory=lambda values: (found.append(values), Literal(1))[1],
            ),
        )
    )
    parse(registry, "compute(1, base=2)")
    parse(registry, "compute(1)")
    parse(registry, "compute(1, 2, 3, 4)")
    assert [tuple(v.value for v in group) for group in found] == [
        (1, 2),
        (1, 10),
        (1, 2, 3, 4),
    ]


def overloaded() -> InterfaceMappingRegistry:
    return InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.INTEGER,),
                lambda _args: Literal(11),
            ),
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.STRING,),
                lambda _args: Literal(22),
            ),
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.INTEGER, ValueKind.INTEGER),
                lambda _args: Literal(33),
            ),
        )
    )


def test_overload_selects_one_exact_static_signature():
    expected = {
        "compute(1)": 11,
        "compute('hello')": 22,
        "compute(1, 2)": 33,
    }
    for call, number in expected.items():
        selected = []
        choices = []
        for types, value in (
            ((ValueKind.INTEGER,), 11),
            ((ValueKind.STRING,), 22),
            ((ValueKind.INTEGER, ValueKind.INTEGER), 33),
        ):
            choices.append(
                InterfaceFunctionMapping(
                    "vendor.ops.compute",
                    types,
                    lambda _args, n=value, out=selected: (out.append(n), Literal(n))[1],
                )
            )
        parse(InterfaceMappingRegistry(choices), call)
        assert selected == [number]


def test_overload_misses_fail_closed():
    with pytest.raises(UnsupportedPython, match="No matching"):
        parse(overloaded(), "compute(True)")


def test_overload_ambiguity_rejected_even_with_distinct_declarations():
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                parameters=(InterfaceParameter("value", ValueKind.INTEGER),),
                factory=lambda _: Literal(1),
            ),
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.INTEGER,),
                lambda _: Literal(2),
            ),
        )
    )
    with pytest.raises(UnsupportedPython, match="Ambiguous"):
        parse(registry, "compute(7)")


def test_variadic_and_fixed_overload_overlap_is_ambiguous_not_first_match():
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.INTEGER,),
                lambda _: Literal(1),
                variadic=InterfaceVariadicParameter("rest", ValueKind.INTEGER),
            ),
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.INTEGER, ValueKind.INTEGER),
                lambda _: Literal(2),
            ),
        )
    )
    with pytest.raises(UnsupportedPython, match="Ambiguous"):
        parse(registry, "compute(7, 8)")


def test_signature_registry_rejects_exact_duplicates_and_invalid_variadics():
    first = InterfaceFunctionMapping(
        "vendor.ops.compute", (ValueKind.INTEGER,), lambda _: Literal(1)
    )
    second = InterfaceFunctionMapping(
        "vendor.ops.compute", (ValueKind.INTEGER,), lambda _: Literal(2)
    )
    with pytest.raises(ValueError, match="Duplicate"):
        InterfaceMappingRegistry((first, second))
    for vararg in (
        InterfaceVariadicParameter("for", ValueKind.INTEGER),
        InterfaceVariadicParameter("_force", ValueKind.INTEGER),
        InterfaceVariadicParameter("value", ValueKind.INTEGER),
        InterfaceVariadicParameter("rest", "integer"),
    ):
        with pytest.raises((TypeError, ValueError), match="variadic"):
            InterfaceMappingRegistry(
                (
                    InterfaceFunctionMapping(
                        "vendor.ops.compute",
                        parameters=(InterfaceParameter("value", ValueKind.INTEGER),),
                        variadic=vararg,
                        factory=lambda _: Literal(1),
                    ),
                )
            )


def test_overload_with_order_reversal_of_effectful_keyword_call_fails_closed():
    registry = InterfaceMappingRegistry(
        (
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                parameters=(
                    InterfaceParameter("first", ValueKind.INTEGER),
                    InterfaceParameter("second", ValueKind.INTEGER),
                ),
                factory=lambda _: Literal(1),
            ),
            InterfaceFunctionMapping(
                "vendor.ops.compute",
                (ValueKind.STRING,),
                lambda _: Literal(2),
            ),
        )
    )
    source = (
        "from vendor.ops import compute\n"
        "def side() -> int:\n"
        "    return 3\n"
        "r: int = compute(second=side(), first=2)"
    )
    with pytest.raises(UnsupportedPython, match="No matching"):
        PythonFrontend(registry).parse(source)


def test_multiple_signatures_normalize_each_source_expression_once(monkeypatch):
    import ast

    calls = []
    original = PythonFrontend._value

    def counted(self, node, expected=None):
        if isinstance(node, ast.Constant) and node.value == 8:
            calls.append(node)
        return original(self, node, expected)

    monkeypatch.setattr(PythonFrontend, "_value", counted)
    parse(overloaded(), "compute(8)")
    assert len(calls) == 1


def test_import_alias_and_variadic_arguments_survive_realization():
    from pyinto import convert
    from tests.support.c_realizer import c_bindings

    c_source = convert(
        'import vendor.ops as ops\nr: int = ops.compute(1, 2, 3)\nprint("ok")',
        interface_mappings=static_varargs(),
        realizations=c_bindings(),
    )
    assert "6" in c_source
    assert "ok" in c_source
