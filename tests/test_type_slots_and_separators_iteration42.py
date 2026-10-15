"""Complete type spelling and per-Slot list placement, without Model rewriting."""

from __future__ import annotations

from typing import ClassVar

import pytest

from pyinto.constructs import (
    Block,
    ConstructError,
    FieldDefinition,
    FunctionDefinition,
    FunctionSignature,
    Literal,
    MappedType,
    Symbol,
    TupleValue,
    ValueKind,
    ValueType,
)
from pyinto.constructs.types import (
    CallableType,
    DictType,
    InstanceType,
    ListType,
    TupleType,
)
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations import Composer, RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)


def basic(kind: ValueKind) -> ValueType:
    return ValueType(kind)


def lst(element: ValueType) -> ValueType:
    return ValueType(ValueKind.LIST, list_type=ListType(element))


def test_full_recursive_value_type_passed_to_dynamic_spelling() -> None:
    seen: list[ValueType] = []

    def spell_type(shape: ValueType, spell: object) -> str:
        seen.append(shape)
        return shape.annotation()

    @realizes(vt.List)
    class ListSpelling:
        type_name = spell_type

    registry = RealizationRegistry("test", (ListSpelling,))
    inner = lst(basic(ValueKind.INTEGER))
    strings = lst(basic(ValueKind.STRING))
    nested = lst(inner)
    assert registry.type_name(inner) == "list[int]"
    assert registry.type_name(Symbol("xs", strings, "list[str]")) == "list[str]"
    assert registry.type_name(nested) == "list[list[int]]"
    assert seen == [inner, strings, nested]
    assert seen[1].list_type is not None
    assert seen[1].list_type.element_type.kind is ValueKind.STRING


def test_all_nested_type_shapes_and_nominal_types_reach_selector() -> None:
    observed: list[ValueType] = []

    def inspect(shape: ValueType, spell: object) -> str:
        observed.append(shape)
        return shape.annotation()

    @realizes(vt.Tuple)
    class TupleTypeSpelling:
        type_name = inspect

    @realizes(vt.Dictionary)
    class DictTypeSpelling:
        type_name = inspect

    @realizes(vt.Function)
    class CallableTypeSpelling:
        type_name = inspect

    @realizes(vt.Instance)
    class InstanceSpelling:
        type_name = inspect

    registry = RealizationRegistry(
        "test",
        (TupleTypeSpelling, DictTypeSpelling, CallableTypeSpelling, InstanceSpelling),
    )
    typed_tuple = ValueType(
        ValueKind.TUPLE,
        tuple_type=TupleType((basic(ValueKind.INTEGER), basic(ValueKind.STRING))),
    )
    typed_dict = ValueType(
        ValueKind.DICT,
        dict_type=DictType(basic(ValueKind.STRING), lst(basic(ValueKind.INTEGER))),
    )
    typed_callable = ValueType(
        ValueKind.FUNCTION, callable_type=CallableType((typed_tuple,), typed_dict)
    )
    nominal = ValueType(
        ValueKind.INSTANCE, instance_type=InstanceType("Record", ("library",))
    )
    for shape in (typed_tuple, typed_dict, typed_callable, nominal):
        assert registry.type_name(shape) == shape.annotation()
    assert observed == [typed_tuple, typed_dict, typed_callable, nominal]


def test_mapped_selector_still_receives_original_mappedtype() -> None:
    mapped = MappedType("demo.Device", "wide")
    received: list[MappedType] = []

    def spell(shape: MappedType, recurse: object) -> str:
        received.append(shape)
        return "device_handle"

    @realizes(mapped)
    class MappedSpelling:
        type_name = spell

    registry = RealizationRegistry("test", (MappedSpelling,))
    assert registry.type_name(Symbol("device", mapped, "Device")) == "device_handle"
    assert registry.type_name(mapped) == "device_handle"
    assert received == [mapped, mapped]


def test_type_selector_rejects_unsupported_shape_and_invalid_output() -> None:
    @realizes(vt.List)
    class NoName:
        type_name = lambda shape, spell: ""

    registry = RealizationRegistry("test", (NoName,))
    with pytest.raises(ConstructError, match="nonempty"):
        registry.type_name(lst(basic(ValueKind.STRING)))
    with pytest.raises(ConstructError, match="No 'test' type representation"):
        registry.type_name(basic(ValueKind.INTEGER))
    with pytest.raises(ConstructError, match="variable type"):
        registry.type_name(Symbol("fn", None))


def test_field_type_slot_uses_full_value_type() -> None:
    @realizes(vt.List)
    class ListSpelling:
        type_name = lambda shape, spell: shape.annotation()

    @realizes(lang.FieldDefinition)
    class FieldSpelling:
        template = "${type} ${name};"

    registry = RealizationRegistry("test", (ListSpelling, FieldSpelling))
    field = FieldDefinition("items", lst(basic(ValueKind.INTEGER)))
    assert Composer(registry).source(field) == "list[int] items;\n"
    assert field.parts()["type"] is field.type


def test_function_return_type_and_parameter_separator() -> None:
    @realizes(vt.List)
    class ListSpelling:
        type_name = lambda shape, spell: shape.annotation()

    @realizes(vt.Integer)
    class IntSpelling:
        type_name = "int"

    @realizes(lang.FunctionDefinition)
    class Func:
        separators: ClassVar[dict[str, str]] = {"parameters": ", "}
        template = "${return_type} ${name}(${parameters}) {${body}}"

    @realizes(lang.Parameter)
    class Param:
        template = "${type} ${name}"

    @realizes(lang.Block)
    class Body:
        template = "${children}"

    registry = RealizationRegistry(
        "test", (ListSpelling, IntSpelling, Func, Param, Body)
    )
    params = (
        Symbol("a", basic(ValueKind.INTEGER), "int"),
        Symbol("b", basic(ValueKind.INTEGER), "int"),
    )
    result_type = lst(basic(ValueKind.STRING))
    signature = FunctionSignature("build", params, "list[str]", result_type)
    definition = FunctionDefinition(signature, Block(()))
    assert definition.parts()["return_type"] is result_type
    assert Composer(registry).source(definition) == "list[str] build(int a, int b) {}\n"
    # The same recipe must handle the empty parameter list.
    empty = FunctionDefinition(
        FunctionSignature("empty", (), "list[str]", result_type), Block(())
    )
    assert Composer(registry).source(empty) == "list[str] empty() {}\n"
    assert definition.signature.return_type is result_type


def test_list_slot_separator_default_unchanged_and_explicit_comma() -> None:
    @realizes(lang.Literal)
    class IntLit:
        variant = "integer"
        render = lambda node, ctx: str(node.value)

    @realizes(lang.TupleValue)
    class DefaultTuple:
        template = "${items}"

    @realizes(lang.TupleValue)
    class CommaTuple:
        template = "(${items})"
        separators: ClassVar[dict[str, str]] = {"items": ", "}

    data = TupleValue((Literal(1), Literal(2)))
    assert (
        Composer(RealizationRegistry("t", (IntLit, DefaultTuple))).source(data)
        == "1\n2\n"
    )
    assert (
        Composer(RealizationRegistry("t", (IntLit, CommaTuple))).source(data)
        == "(1, 2)\n"
    )
    assert data.parts()["items"] == (Literal(1), Literal(2))
    empty = TupleValue(())
    assert (
        Composer(RealizationRegistry("t", (IntLit, CommaTuple))).source(empty) == "()\n"
    )


def test_separators_reject_unknown_unused_nontuple_and_wrong_role() -> None:
    @realizes(lang.TupleValue)
    class UnknownSlot:
        separators: ClassVar[dict[str, str]] = {"missing": ", "}
        template = "${items}"

    with pytest.raises(ValueError, match="separators"):
        RealizationRegistry("t", (UnknownSlot,))

    @realizes(lang.TupleValue)
    class UnusedSlot:
        separators: ClassVar[dict[str, str]] = {"items": ", "}
        template = "ok"

    with pytest.raises(ValueError, match="separators"):
        RealizationRegistry("t", (UnusedSlot,))

    @realizes(lang.FieldDefinition)
    class WrongSlotType:
        separators: ClassVar[dict[str, str]] = {"type": ", "}
        template = "${type}"

    registry = RealizationRegistry("t", (WrongSlotType,))
    with pytest.raises(ConstructError, match="separator requires a tuple"):
        Composer(registry).source(FieldDefinition("x", basic(ValueKind.INTEGER)))

    @realizes(vt.Integer)
    class WrongRole:
        separators: ClassVar[dict[str, str]] = {"anything": ", "}
        type_name = "int"

    with pytest.raises(ValueError, match="separators"):
        RealizationRegistry("t", (WrongRole,))


def test_separator_malformed_and_not_used_by_dynamic_renderer() -> None:
    @realizes(lang.TupleValue)
    class BadValue:
        separators: ClassVar[dict[str, str]] = {"items": 123}
        template = "${items}"

    with pytest.raises(ValueError, match="separators"):
        RealizationRegistry("t", (BadValue,))

    @realizes(lang.TupleValue)
    class DynamicNoSlot:
        separators: ClassVar[dict[str, str]] = {"items": ", "}
        render = lambda node, ctx: "none"

    with pytest.raises(ConstructError, match="unused Slots"):
        Composer(RealizationRegistry("t", (DynamicNoSlot,))).source(TupleValue(()))
