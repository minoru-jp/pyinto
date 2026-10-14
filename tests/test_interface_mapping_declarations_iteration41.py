"""Shikumi maps/signature declarations preserve existing mapping behavior."""

from __future__ import annotations

import math

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import Literal, ValueKind
from pyinto.interface_mapping import (
    InterfaceFunctionMapping,
    InterfaceMappingRegistry,
    InterfaceParameter,
    InterfaceVariadicParameter,
    factory,
    maps,
    signature,
)
from pyinto.interface_mapping.declarations import function_declarations


def compute(value: int | str, *more: int) -> int:
    """Normal Python callable; never executed by pyinto normalization."""
    if isinstance(value, str):
        return len(value)
    return value + sum(more)


captured: list[tuple[object, ...]] = []


def integer_factory(values):
    captured.append(tuple(values))
    return Literal(sum(item.value for item in values))


def string_factory(values):
    captured.append(tuple(values))
    return Literal(len(values[0].value))


@maps(compute)
class ComputeMappings:
    @signature(
        InterfaceParameter("value", ValueKind.INTEGER),
        variadic=InterfaceVariadicParameter("more", ValueKind.INTEGER),
    )
    class Integers:
        factory @= integer_factory

    @signature(InterfaceParameter("value", ValueKind.STRING))
    class String:
        factory @= string_factory


@maps(math.sqrt)
class SqrtMappings:
    @signature(InterfaceParameter("value", ValueKind.FLOAT))
    class Floating:
        factory @= lambda args: args[0]


def test_public_shikumi_names_are_exports():
    from pyinto import interface_mapping

    assert interface_mapping.maps is maps
    assert interface_mapping.signature is signature
    assert interface_mapping.factory is factory


def test_nested_declarations_materialize_into_existing_function_entries():
    result = function_declarations(ComputeMappings)
    assert len(result) == 2
    assert all(isinstance(x, InterfaceFunctionMapping) for x in result)
    assert [x.source for x in result] == [f"{__name__}.compute"] * 2
    assert result[0].variadic is not None
    assert result[1].variadic is None
    assert result[0].factory is integer_factory


def test_registered_declaration_has_same_signature_and_can_normalize():
    registry = InterfaceMappingRegistry.from_declarations((ComputeMappings,))
    assert len(registry.signatures(f"{__name__}.compute")) == 2
    parsed = PythonFrontend(registry)
    captured.clear()
    parsed.parse(f"import {__name__} as lib\nr: int = lib.compute(1, 2, 3)")
    assert tuple(x.value for x in captured[-1]) == (1, 2, 3)
    parsed.parse(f"from {__name__} import compute\nr: int = compute('abc')")
    assert captured[-1][0].value == "abc"


def test_real_stdlib_function_is_identity_not_magic_library_handling():
    registry = InterfaceMappingRegistry.from_declarations((SqrtMappings,))
    assert registry.get("math.sqrt") is not None
    assert PythonFrontend(registry).parse("import math as m\nr: float = m.sqrt(9.0)")


def test_named_default_and_positional_only_variants():
    @maps(compute)
    class Defaults:
        @signature(
            InterfaceParameter("value", ValueKind.INTEGER),
            InterfaceParameter("base", ValueKind.INTEGER, Literal(8)),
        )
        class Named:
            factory @= integer_factory

    @maps(math.floor)
    class Positional:
        @signature(ValueKind.FLOAT)
        class Float:
            factory @= lambda values: Literal(3)

    registry = InterfaceMappingRegistry.from_declarations((Defaults, Positional))
    captured.clear()
    PythonFrontend(registry).parse(
        f"from {__name__} import compute\nr: int = compute(value=2)"
    )
    assert tuple(x.value for x in captured[-1]) == (2, 8)
    assert PythonFrontend(registry).parse("import math\nr: int = math.floor(9.9)")


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("compute()", "No matching"),
        ("compute(True)", "No matching"),
        ("compute(1, extra=2)", "No matching"),
        ("compute(1, *[2, 3])", "Expanded"),
    ],
)
def test_existing_fail_closed_rejections_preserved(expression, expected):
    registry = InterfaceMappingRegistry.from_declarations((ComputeMappings,))
    with pytest.raises(UnsupportedPython, match=expected):
        PythonFrontend(registry).parse(
            f"from {__name__} import compute\nr: int = {expression}"
        )


def test_duplicate_nested_signatures_rejected_by_existing_registry():
    @maps(compute)
    class Duplicates:
        @signature(ValueKind.INTEGER)
        class One:
            factory @= integer_factory

        @signature(ValueKind.INTEGER)
        class Two:
            factory @= string_factory

    with pytest.raises(ValueError, match="Duplicate interface mapping signature"):
        InterfaceMappingRegistry.from_declarations((Duplicates,))


def test_matching_signatures_ambiguity_still_fails_closed():
    @maps(compute)
    class Ambiguous:
        @signature(InterfaceParameter("value", ValueKind.INTEGER))
        class Named:
            factory @= integer_factory

        @signature(ValueKind.INTEGER)
        class Positional:
            factory @= integer_factory

    registry = InterfaceMappingRegistry.from_declarations((Ambiguous,))
    with pytest.raises(UnsupportedPython, match="Ambiguous"):
        PythonFrontend(registry).parse(
            f"from {__name__} import compute\nr: int = compute(2)"
        )


def test_reject_missing_nested_declaration():
    @maps(compute)
    class Empty:
        pass

    with pytest.raises(ValueError, match="at least one"):
        InterfaceMappingRegistry.from_declarations((Empty,))


def test_reject_missing_signature():
    @maps(compute)
    class Bad:
        class Child:
            factory @= integer_factory

    with pytest.raises(ValueError, match="signature"):
        InterfaceMappingRegistry.from_declarations((Bad,))


def test_reject_missing_factory_and_noncallable_factory():
    @maps(compute)
    class BadMissing:
        @signature(ValueKind.INTEGER)
        class Child:
            pass

    @maps(compute)
    class BadFactory:
        @signature(ValueKind.INTEGER)
        class Child:
            factory @= 123

    for parent in (BadMissing, BadFactory):
        with pytest.raises(ValueError, match="callable factory"):
            InterfaceMappingRegistry.from_declarations((parent,))


def test_reject_factory_on_parent_and_source_on_child():
    @maps(compute)
    class BadParent:
        factory @= integer_factory

        @signature(ValueKind.INTEGER)
        class One:
            factory @= integer_factory

    @maps(compute)
    class BadChild:
        @maps(compute)
        @signature(ValueKind.INTEGER)
        class One:
            factory @= integer_factory

    for parent in (BadParent, BadChild):
        with pytest.raises(ValueError):
            InterfaceMappingRegistry.from_declarations((parent,))


def test_reject_class_alias_instead_of_directly_nested_signature():
    @signature(ValueKind.INTEGER)
    class Different:
        factory @= integer_factory

    @maps(compute)
    class Bad:
        Other = Different

    with pytest.raises(ValueError, match="directly nested"):
        InterfaceMappingRegistry.from_declarations((Bad,))


def test_invalid_external_source_avoids_ambiguous_python_function_identity():
    def nested(value: int) -> int:
        return value

    class CallableObject:
        def __call__(self):
            return 2

    for source in (nested, CallableObject(), object()):

        @maps(source)
        class Bad:
            @signature(ValueKind.INTEGER)
            class Entry:
                factory @= integer_factory

        with pytest.raises(ValueError, match="maps requires"):
            InterfaceMappingRegistry.from_declarations((Bad,))


def test_declaration_errors_do_not_mutate_registry_or_auto_register():
    empty = InterfaceMappingRegistry()
    assert not empty.has_namespace(__name__)
    with pytest.raises(UnsupportedPython):
        PythonFrontend(empty).parse(f"import {__name__} as lib\nlib.compute(2)")


def test_invalid_signature_mixing_rejected():
    with pytest.raises(TypeError, match="signature requires"):
        signature(InterfaceParameter("value", ValueKind.INTEGER), ValueKind.STRING)


def test_invalid_signature_parameter_names_and_defaults_reuse_old_validation():
    @maps(compute)
    class Invalid:
        @signature(InterfaceParameter("for", ValueKind.INTEGER))
        class Bad:
            factory @= integer_factory

    with pytest.raises(ValueError, match="Invalid or duplicate"):
        InterfaceMappingRegistry.from_declarations((Invalid,))
