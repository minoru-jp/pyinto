"""SDD 16: typed mutable dictionaries, without a Target Realization."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    ConstructError,
    DictElement,
    DictElementAssign,
    DictEntry,
    DictType,
    DictValue,
    FunctionCall,
    FunctionValueCall,
    Initialize,
    ListType,
    Literal,
    Reference,
    Symbol,
    TupleElement,
    TupleType,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def parse(source: str):
    return PythonFrontend().parse(source)


def no_ast(tree: object) -> bool:
    if isinstance(tree, ast.AST):
        return False
    if isinstance(tree, (tuple, list)):
        return all(no_ast(value) for value in tree)
    if is_dataclass(tree) and not isinstance(tree, type):
        return all(no_ast(getattr(tree, f.name)) for f in fields(tree))
    return True


def shape(value: ValueType | None = None) -> DictType:
    return DictType(ValueType(ValueKind.STRING), value or ValueType(ValueKind.INTEGER))


def ref() -> Reference:
    return Reference(
        Symbol("record", ValueType(ValueKind.DICT, dict_type=shape()), "dict[str, int]")
    )


def test_cst_032_dictionary_type_and_nested_annotations() -> None:
    t = shape()
    assert t.annotation() == "dict[str, int]"
    nested = ValueType(
        ValueKind.DICT,
        dict_type=DictType(
            ValueType(ValueKind.INTEGER),
            ValueType(ValueKind.DICT, dict_type=t),
        ),
    )
    assert nested.annotation() == "dict[int, dict[str, int]]"
    assert nested.kind is ValueKind.DICT
    assert nested != ValueType(ValueKind.DICT, dict_type=t)
    assert no_ast(nested)


@pytest.mark.parametrize("kind", [ValueKind.DICT, ValueKind.LIST, ValueKind.INTEGER])
def test_cst_032_dictionary_shape_guard(kind: ValueKind) -> None:
    if kind is ValueKind.DICT:
        with pytest.raises(ConstructError, match="key/value shape"):
            ValueType(kind)
        with pytest.raises(ValueError, match="shape"):
            Symbol("d", ValueType(kind), "dict[str, int]")
    else:
        kwargs = (
            {"list_type": ListType(ValueType(ValueKind.INTEGER))}
            if kind is ValueKind.LIST
            else {}
        )
        with pytest.raises(ConstructError, match="key/value shape"):
            ValueType(kind, dict_type=shape(), **kwargs)
        with pytest.raises(ValueError, match="shape"):
            Symbol("d", ValueType(kind, dict_type=shape()), "int", **kwargs)


@pytest.mark.parametrize(
    "key, value",
    [
        (
            ValueType(ValueKind.TUPLE, tuple_type=TupleType(())),
            ValueType(ValueKind.INTEGER),
        ),
        (
            ValueType(ValueKind.LIST, list_type=ListType(ValueType(ValueKind.INTEGER))),
            ValueType(ValueKind.INTEGER),
        ),
        (ValueType(ValueKind.ANY), ValueType(ValueKind.INTEGER)),
        (ValueType(ValueKind.BOOLEAN), ValueType(ValueKind.INTEGER)),
        (ValueType(ValueKind.NONE), ValueType(ValueKind.INTEGER)),
        ("str", ValueType(ValueKind.INTEGER)),
    ],
)
def test_cst_032_dictionary_rejects_non_scalar_keys(key: object, value: object) -> None:
    with pytest.raises(ConstructError, match="keys require"):
        DictType(key, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [ValueType(ValueKind.NONE), "bad"])
def test_cst_032_dictionary_rejects_unsupported_values(value: object) -> None:
    with pytest.raises(ConstructError, match="values require"):
        DictType(ValueType(ValueKind.INTEGER), value)  # type: ignore[arg-type]


def test_cst_032_dictionary_literal_retains_entry_order_and_duplicate_keys() -> None:
    entries = (
        DictEntry(Literal("a"), Literal(1)),
        DictEntry(Literal("b"), Literal(2)),
        DictEntry(Literal("a"), Literal(3)),
    )
    d = DictValue(entries, shape().key_type, shape().value_type)
    assert d.kind is ValueKind.DICT
    assert d.value_type == ValueType(ValueKind.DICT, dict_type=shape())
    assert d.parts() == {"entries": entries}
    assert entries[0].parts() == {"key": Literal("a"), "value": Literal(1)}
    assert entries[2].key == entries[0].key
    assert no_ast(d)
    assert DictValue((), shape().key_type, shape().value_type).entries == ()


def test_cst_032_dictionary_literal_rejects_mismatches() -> None:
    for entry in (
        DictEntry(Literal(1), Literal(2)),
        DictEntry(Literal("a"), Literal("bad")),
    ):
        with pytest.raises(ConstructError, match="entry type mismatch"):
            DictValue((entry,), shape().key_type, shape().value_type)
    with pytest.raises(ConstructError, match="DictEntry"):
        DictValue(("bad",), shape().key_type, shape().value_type)  # type: ignore[arg-type]
    with pytest.raises(ConstructError, match="key and value Values"):
        DictEntry("bad", Literal(1))  # type: ignore[arg-type]


def test_cst_033_access_propagates_nested_value_types() -> None:
    nested = shape(
        ValueType(ValueKind.LIST, list_type=ListType(ValueType(ValueKind.INTEGER)))
    )
    sym = Symbol("d", ValueType(ValueKind.DICT, dict_type=nested), nested.annotation())
    source, key = Reference(sym), Literal("a")
    access = DictElement(source, key)
    assert access.kind is ValueKind.LIST
    assert access.list_type == ListType(ValueType(ValueKind.INTEGER))
    assert access.value_type == nested.value_type
    assert access.parts() == {"source": source, "key": key}


@pytest.mark.parametrize(
    "source, key, fragment",
    [
        (Literal(4), Literal("x"), "dict Value"),
        (ref(), Literal(4), "key type mismatch"),
    ],
)
def test_cst_033_access_rejects_invalid_types(
    source: object, key: object, fragment: str
) -> None:
    with pytest.raises(ConstructError, match=fragment):
        DictElement(source, key)  # type: ignore[arg-type]


def test_cst_033_assignment_preserves_mutation_parts_not_rebinding() -> None:
    target = ref()
    mutation = DictElementAssign(target, Literal("k"), Literal(8))
    assert mutation.parts() == {
        "target": target,
        "key": Literal("k"),
        "value": Literal(8),
    }
    assert mutation.target.symbol is target.symbol
    for bad_target, bad_key, bad_value, text in (
        (Literal(1), Literal("k"), Literal(2), "dict Reference"),
        (target, Literal(2), Literal(2), "key type mismatch"),
        (target, Literal("k"), Literal("bad"), "value type mismatch"),
    ):
        with pytest.raises(ConstructError, match=text):
            DictElementAssign(bad_target, bad_key, bad_value)  # type: ignore[arg-type]


def test_frt_024_declared_dict_and_alias_mutation() -> None:
    model = parse(
        "a: dict[str, int] = {'a': 1, 'b': 2}\nb: dict[str, int] = a\na['c'] = 3\nx: int = b['c']"
    )
    init, alias, mutation, lookup = model.body.children
    assert isinstance(init, Initialize) and isinstance(init.value, DictValue)
    assert init.value.dict_type == shape()
    assert isinstance(alias, Initialize) and isinstance(alias.value, Reference)
    assert alias.value.symbol is init.symbol
    assert isinstance(mutation, DictElementAssign)
    assert mutation.target.symbol is init.symbol
    assert isinstance(lookup, Initialize) and isinstance(lookup.value, DictElement)
    assert lookup.value.source.symbol is alias.symbol
    assert no_ast(model)


def test_frt_024_untyped_nonempty_dictionary_literal_is_inferred() -> None:
    model = parse("a: dict[int, str] = {1: 'one', 2: 'two'}")
    val = model.body.children[0].value
    assert isinstance(val, DictValue)
    assert val.dict_type.annotation() == "dict[int, str]"
    assert [e.key.value for e in val.entries] == [1, 2]


def test_frt_024_empty_dictionary_uses_expected_type_in_declaration_and_assignment() -> (
    None
):
    model = parse("a: dict[str, int] = {}\na = {}")
    assert all(
        isinstance(item.value, DictValue) and item.value.entries == ()
        for item in model.body.children
    )


def test_frt_024_dictionary_nested_shapes_with_list_tuple_and_callable() -> None:
    program = parse(
        "from typing import Callable\n"
        "def select(data: dict[str, tuple[int, list[int]]]) -> dict[str, tuple[int, list[int]]]:\n"
        "    return data\n"
        "f: Callable[[dict[str, tuple[int, list[int]]]], dict[str, tuple[int, list[int]]]] = select\n"
        "a: dict[str, tuple[int, list[int]]] = f({'a': (1, [2, 3])})\n"
        "b: list[int] = a['a'][1]"
    )
    fcall = program.body.children[-2].value
    assert isinstance(fcall, FunctionValueCall)
    assert isinstance(fcall.arguments[0], DictValue)
    assert fcall.kind is ValueKind.DICT
    assert isinstance(program.body.children[-1].value, TupleElement)
    assert isinstance(program.body.children[-1].value.source, DictElement)
    assert no_ast(program)


def test_frt_024_nested_dictionary_literals_and_returns() -> None:
    program = parse(
        "def build() -> dict[str, dict[int, str]]:\n"
        "    return {'a': {1: 'x'}}\n"
        "d: dict[str, dict[int, str]] = build()\n"
        "x: str = d['a'][1]"
    )
    call = program.body.children[1].value
    assert isinstance(call, FunctionCall)
    assert call.dict_type.annotation() == "dict[str, dict[int, str]]"
    assert no_ast(program)


def test_frt_024_empty_dict_in_direct_and_indirect_calls() -> None:
    program = parse(
        "from typing import Callable\n"
        "def identity(d: dict[str, int]) -> dict[str, int]:\n"
        "    return d\n"
        "f: Callable[[dict[str, int]], dict[str, int]] = identity\n"
        "a: dict[str, int] = identity({})\n"
        "b: dict[str, int] = f({})"
    )
    direct, indirect = (s.value for s in program.body.children[-2:])
    assert isinstance(direct, FunctionCall)
    assert isinstance(indirect, FunctionValueCall)
    assert direct.arguments[0].entries == ()
    assert indirect.arguments[0].entries == ()


def test_frt_024_nested_function_reads_and_mutates_enclosing_dictionary() -> None:
    program = parse(
        "def outer(data: dict[str, int]) -> int:\n"
        "    def inner() -> int:\n"
        "        data['a'] = 7\n"
        "        return data['a']\n"
        "    return inner()"
    )
    outer = program.body.children[0]
    inner = outer.body.children[0]
    write = inner.body.children[0]
    assert isinstance(write, DictElementAssign)
    assert write.target.symbol is outer.signature.parameters[0]
    assert lexical_captures(inner) == (outer.signature.parameters[0],)


@pytest.mark.parametrize(
    "source, fragment",
    [
        ("d: dict[str, int] = {'a': 'wrong'}", "entry type mismatch"),
        ("d: dict[str, int] = {1: 2}", "entry type mismatch"),
        ("d: dict[str, int] = {'a': 1, 'b': 'wrong'}", "entry type mismatch"),
        ("d: dict[str, int] = {'a': 1}\nd[1] = 3", "key type mismatch"),
        ("d: dict[str, int] = {'a': 1}\nd['b'] = 'wrong'", "value type mismatch"),
        ("d: dict[str, int] = {'a': 1}\nx: int = d[1]", "key type mismatch"),
        ("d: dict[str, int] = {'a': 1}\nd = {1: 2}", "entry type mismatch"),
        ("d: dict[str, int] = {**{'a': 1}}", "Dictionary unpacking"),
        ("d: dict[str, int] = dict(a=1)", "Unregistered interface mapping"),
        (
            "d: dict[str, int] = {'a': 1}\nd.update({'b': 2})",
            "Unregistered interface mapping",
        ),
        ("d: dict[str, int] = {'a': 1}\nd['a'] += 1", "Only named scalar"),
        ("d: dict[str, int] = {'a': 1}\nd['a':'c'] = 2", "Unsupported expression"),
        (
            "d: dict[str, int] = {'a': 1}\nd['a'] = 2\nd['b'] = None",
            "value type mismatch",
        ),
        (
            "d: dict[str, int] = {'a': 1}\nd[0]['b'] = 2",
            "Collection mutation requires a direct variable",
        ),
        (
            "d: dict[str, int] = {'a': 1}\nx: int = d.get('a')",
            "Only directly imported interface mapping",
        ),
        ("d: dict[str, int] = {'a': 1}\nx = d['a']", "explicit type annotation"),
        ("d: dict[str, int] = {x: 1 for x in ['a']}", "Unsupported expression"),
        ("d: dict[str, int] = {True: 1}", "entry type mismatch"),
        ("d: dict[bool, int] = {}", "keys require"),
        ("d: dict[list[int], int] = {}", "keys require"),
        ("d: dict[int, None] = {}", "values require"),
        ("d: dict[int] = {}", "exactly two"),
        ("d: dict[int, str, int] = {}", "exactly two"),
        ("d: dict = {}", "Unknown type annotation"),
        ("d: dict[str, int] = {}\nd['a', 'b'] = 1", "key type mismatch"),
        ("d: dict[str, int] = {}\nx: int = d['a':'b']", "Slicing requires"),
        ("d = {}", "explicit type annotation"),
        ("d: list[dict[str, int]] = [{1: 2}]", "entry type mismatch"),
        (
            "d: dict[str, int] = {'a': 1}\ne: dict[int, int] = d",
            "Annotated type does not match",
        ),
        ("def f(x: dict[str, int]) -> int:\n    return x[1]", "key type mismatch"),
    ],
)
def test_frt_025_unsupported_and_mismatched_forms_rejected(
    source: str, fragment: str
) -> None:
    with pytest.raises(UnsupportedPython, match=fragment):
        parse(source)


def test_frt_025_missing_realization_does_not_mutate_model() -> None:
    model = parse("d: dict[str, int] = {'a': 1}\nx: int = d['a']\nd['b'] = 2")
    snapshot = repr(model)
    with pytest.raises(ConstructError, match="No 'c' realization for DictValue"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot
    assert no_ast(model)


def test_frt_025_source_is_never_executed() -> None:
    # Unresolved names are errors, never an invitation to import or evaluate.
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        parse("d: dict[str, int] = {'a': dangerous_call()}")


def test_frt_024_function_value_stored_in_dictionary_can_be_called() -> None:
    program = parse(
        "from typing import Callable\n"
        "def inc(x: int) -> int:\n"
        "    return x + 1\n"
        "operations: dict[str, Callable[[int], int]] = {'inc': inc}\n"
        "result: int = operations['inc'](5)"
    )
    call = program.body.children[-1].value
    assert isinstance(call, FunctionValueCall)
    assert isinstance(call.callee, DictElement)
    assert call.callee.callable_type == program.body.children[0].signature.callable_type
    assert call.arguments == (Literal(5),)
    assert no_ast(program)


def test_frt_024_capture_through_dictionary_entry_and_key_expression() -> None:
    program = parse(
        "def outer(key: str, value: int) -> dict[str, int]:\n"
        "    def inner() -> dict[str, int]:\n"
        "        return {key: value}\n"
        "    return inner()"
    )
    outer = program.body.children[0]
    inner = outer.body.children[0]
    assert lexical_captures(inner) == outer.signature.parameters
