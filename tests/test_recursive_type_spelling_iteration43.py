"""Nested Model type names are resolved through one Target registry."""

from __future__ import annotations

import pytest

from pyinto.constructs import ConstructError, FieldDefinition, MappedType, Symbol
from pyinto.constructs.types import (
    CallableType,
    DictType,
    ListType,
    TupleType,
    ValueKind,
    ValueType,
)
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations import Composer, RealizationRegistry
from pyinto.realizations.regulation import realizes


def primitive(kind: ValueKind) -> ValueType:
    return ValueType(kind)


def list_of(inner: ValueType) -> ValueType:
    return ValueType(ValueKind.LIST, list_type=ListType(inner))


def test_nested_list_uses_same_target_rules_at_every_level() -> None:
    called: list[ValueType] = []

    def spell_list(shape: ValueType, spell: object) -> str:
        assert callable(spell)
        called.append(shape)
        assert shape.list_type is not None
        return f"Vec<{spell(shape.list_type.element_type)}>"

    @realizes(vt.Integer)
    class Integer:
        type_name = "i64"

    @realizes(vt.List)
    class List:
        type_name = spell_list

    registry = RealizationRegistry("rust-like", (Integer, List))
    integer = primitive(ValueKind.INTEGER)
    inner = list_of(integer)
    outer = list_of(inner)
    assert registry.type_name(integer) == "i64"
    assert registry.type_name(inner) == "Vec<i64>"
    assert registry.type_name(outer) == "Vec<Vec<i64>>"
    assert called == [inner, outer, inner]
    # Each independent top-level request has its own recursion guard.
    assert registry.type_name(outer) == "Vec<Vec<i64>>"


def test_dict_tuple_and_callable_recursively_delegate_to_same_registry() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = "i64"

    @realizes(vt.String)
    class String:
        type_name = "String"

    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: f"Vec<{spell(shape.list_type.element_type)}>"

    @realizes(vt.Dictionary)
    class Dictionary:
        type_name = lambda shape, spell: (
            f"Map<{spell(shape.dict_type.key_type)}, "
            f"{spell(shape.dict_type.value_type)}>"
        )

    @realizes(vt.Tuple)
    class Tuple:
        type_name = lambda shape, spell: (
            "(" + ", ".join(spell(t) for t in shape.tuple_type.element_types) + ")"
        )

    @realizes(vt.Function)
    class Function:
        type_name = lambda shape, spell: (
            "fn("
            + ", ".join(spell(t) for t in shape.callable_type.parameter_types)
            + ") -> "
            + spell(shape.callable_type.return_type)
        )

    registry = RealizationRegistry(
        "test", (Integer, String, List, Dictionary, Tuple, Function)
    )
    integer = primitive(ValueKind.INTEGER)
    string = primitive(ValueKind.STRING)
    nested_dict = ValueType(
        ValueKind.DICT,
        dict_type=DictType(string, list_of(integer)),
    )
    tuple_type = ValueType(
        ValueKind.TUPLE,
        tuple_type=TupleType((integer, nested_dict)),
    )
    function = ValueType(
        ValueKind.FUNCTION,
        callable_type=CallableType((tuple_type,), nested_dict),
    )
    assert registry.type_name(nested_dict) == "Map<String, Vec<i64>>"
    assert registry.type_name(tuple_type) == "(i64, Map<String, Vec<i64>>)"
    assert registry.type_name(function) == (
        "fn((i64, Map<String, Vec<i64>>)) -> Map<String, Vec<i64>>"
    )


def test_nested_spelling_reaches_field_slot_in_composer() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = "i64"

    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: f"Vec<{spell(shape.list_type.element_type)}>"

    @realizes(lang.FieldDefinition)
    class Field:
        template = "${type} ${name};"

    registry = RealizationRegistry("test", (Integer, List, Field))
    field = FieldDefinition("values", list_of(list_of(primitive(ValueKind.INTEGER))))
    assert Composer(registry).source(field) == "Vec<Vec<i64>> values;\n"


def test_missing_nested_rule_fails_closed_without_substituting_python_name() -> None:
    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: f"Vec<{spell(shape.list_type.element_type)}>"

    registry = RealizationRegistry("test", (List,))
    with pytest.raises(
        ConstructError, match="No 'test' type representation for 'integer'"
    ):
        registry.type_name(list_of(primitive(ValueKind.INTEGER)))


def test_nested_invalid_output_is_rejected() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = lambda shape, spell: ""

    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: spell(shape.list_type.element_type)

    registry = RealizationRegistry("test", (Integer, List))
    with pytest.raises(ConstructError, match="nonempty"):
        registry.type_name(list_of(primitive(ValueKind.INTEGER)))


def test_recursive_self_call_rejected_before_python_recursion_limit() -> None:
    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: spell(shape)

    registry = RealizationRegistry("test", (List,))
    with pytest.raises(ConstructError, match="Cyclic type spelling"):
        registry.type_name(list_of(primitive(ValueKind.INTEGER)))
    with pytest.raises(ConstructError, match="Cyclic type spelling"):
        registry.type_name(list_of(primitive(ValueKind.STRING)))


def test_repeated_sibling_type_is_not_a_cycle() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = "i64"

    @realizes(vt.Tuple)
    class Tuple:
        type_name = lambda shape, spell: ", ".join(
            spell(element) for element in shape.tuple_type.element_types
        )

    registry = RealizationRegistry("test", (Integer, Tuple))
    integer = primitive(ValueKind.INTEGER)
    pair = ValueType(ValueKind.TUPLE, tuple_type=TupleType((integer, integer)))
    assert registry.type_name(pair) == "i64, i64"


def test_two_selector_cycle_is_rejected() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = lambda shape, spell: spell(list_of(shape))

    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: spell(shape.list_type.element_type)

    registry = RealizationRegistry("test", (Integer, List))
    with pytest.raises(ConstructError, match="Cyclic type spelling"):
        registry.type_name(primitive(ValueKind.INTEGER))


def test_mapped_selector_can_delegate_to_registered_value_type() -> None:
    mapped = MappedType("demo.Device", "wide")

    @realizes(vt.Integer)
    class Integer:
        type_name = "i64"

    @realizes(mapped)
    class External:
        type_name = lambda shape, spell: (
            f"Handle<{spell(primitive(ValueKind.INTEGER))}>"
        )

    registry = RealizationRegistry("test", (Integer, External))
    assert registry.type_name(mapped) == "Handle<i64>"
    assert registry.type_name(Symbol("device", mapped, "Device")) == "Handle<i64>"


def test_speller_supports_symbol_and_rejects_unsupported_value() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = "i64"

    @realizes(vt.List)
    class List:
        type_name = lambda shape, spell: spell(
            Symbol("n", shape.list_type.element_type, "int")
        )

    registry = RealizationRegistry("test", (Integer, List))
    assert registry.type_name(list_of(primitive(ValueKind.INTEGER))) == "i64"

    @realizes(vt.String)
    class String:
        type_name = lambda shape, spell: spell(123)

    registry = RealizationRegistry("test", (String,))
    with pytest.raises(ConstructError, match="needs a Model type or Symbol"):
        registry.type_name(primitive(ValueKind.STRING))


def test_legacy_single_argument_callback_is_not_implicitly_adapted() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = lambda shape: "i64"

    registry = RealizationRegistry("test", (Integer,))
    with pytest.raises(ConstructError, match="positional argument"):
        registry.type_name(primitive(ValueKind.INTEGER))


def test_fixed_type_spellings_are_unchanged() -> None:
    @realizes(vt.Integer)
    class Integer:
        type_name = "long long"

    registry = RealizationRegistry("test", (Integer,))
    assert registry.type_name(primitive(ValueKind.INTEGER)) == "long long"
    assert (
        registry.type_name(Symbol("x", primitive(ValueKind.INTEGER), "int"))
        == "long long"
    )
