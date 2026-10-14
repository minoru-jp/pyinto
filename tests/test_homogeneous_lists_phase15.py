"""SDD 15: typed homogeneous mutable lists, without new Target Realizations."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    Assign,
    CallableType,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    FunctionValueCall,
    Initialize,
    ListElement,
    ListElementAssign,
    ListType,
    ListValue,
    Literal,
    Reference,
    Return,
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
        return all(no_ast(x) for x in tree)
    if is_dataclass(tree) and not isinstance(tree, type):
        return all(no_ast(getattr(tree, f.name)) for f in fields(tree))
    return True


def test_cst_030_list_type_is_recursive_target_neutral() -> None:
    integer = ValueType(ValueKind.INTEGER)
    shape = ListType(integer)
    nested = ValueType(
        ValueKind.LIST, list_type=ListType(ValueType(ValueKind.LIST, list_type=shape))
    )
    assert shape.annotation() == "list[int]"
    assert nested.annotation() == "list[list[int]]"
    assert not isinstance(nested, ast.AST)
    assert ValueType(ValueKind.LIST, list_type=shape).annotation() == "list[int]"
    assert shape != ListType(ValueType(ValueKind.STRING))
    assert no_ast(nested)


@pytest.mark.parametrize(
    "kind", [ValueKind.LIST, ValueKind.TUPLE, ValueKind.FUNCTION, ValueKind.INTEGER]
)
def test_cst_030_list_shape_must_match_value_kind(kind: ValueKind) -> None:
    if kind is ValueKind.LIST:
        with pytest.raises(ConstructError, match="element shape"):
            ValueType(kind)
        with pytest.raises(ValueError, match="element shape"):
            Symbol("xs", ValueType(kind), "list[int]")
    else:
        kwargs = (
            {"tuple_type": TupleType(())}
            if kind is ValueKind.TUPLE
            else {"callable_type": CallableType((), ValueType(ValueKind.INTEGER))}
            if kind is ValueKind.FUNCTION
            else {}
        )
        with pytest.raises(ConstructError, match="element shape"):
            ValueType(kind, list_type=ListType(ValueType(ValueKind.INTEGER)), **kwargs)


@pytest.mark.parametrize("element", [ValueType(ValueKind.NONE), "bad"])
def test_cst_030_invalid_element_shapes_rejected(element: object) -> None:
    with pytest.raises(ConstructError, match="supported element"):
        ListType(element)  # type: ignore[arg-type]


def test_cst_030_list_literal_has_explicit_homogeneous_shape_and_order() -> None:
    element = ValueType(ValueKind.INTEGER)
    v = ListValue((Literal(3), Literal(1), Literal(4)), element)
    assert v.kind is ValueKind.LIST
    assert v.value_type == ValueType(ValueKind.LIST, list_type=ListType(element))
    assert v.parts() == {"items": v.items}
    assert v.items[0] == Literal(3)
    assert v.items[2] == Literal(4)
    assert ListValue((), element).list_type == ListType(element)
    with pytest.raises(ConstructError, match="element type mismatch"):
        ListValue((Literal(3), Literal("bad")), element)
    with pytest.raises(ConstructError, match="must be Values"):
        ListValue(("bad",), element)  # type: ignore[arg-type]


def test_cst_030_symbol_and_reference_are_structurally_typed() -> None:
    shape = ListType(ValueType(ValueKind.STRING))
    sym = Symbol("strings", ValueType(ValueKind.LIST, list_type=shape), "list[str]")
    ref = Reference(sym)
    assert ref.list_type is shape
    assert ref.value_type == ValueType(ValueKind.LIST, list_type=shape)
    assert ref.parts()["name"].value == "strings"
    assert no_ast(ref)


def test_cst_031_dynamic_index_and_element_write_keep_order() -> None:
    shape = ListType(ValueType(ValueKind.INTEGER))
    sym = Symbol("nums", ValueType(ValueKind.LIST, list_type=shape), "list[int]")
    index = Literal(-1)
    ref = Reference(sym)
    read = ListElement(ref, index)
    write = ListElementAssign(ref, index, Literal(9))
    assert read.parts() == {"source": ref, "index": index}
    assert read.kind is ValueKind.INTEGER
    assert write.parts() == {"target": ref, "index": index, "value": Literal(9)}
    assert write.parts()["target"].symbol is sym
    assert read.HOLES == frozenset({"source", "index"})
    assert write.HOLES == frozenset({"target", "index", "value"})


@pytest.mark.parametrize(
    "source,index,value,message",
    [
        (Literal(1), Literal(0), None, "list Value"),
        (
            ListValue((), ValueType(ValueKind.INTEGER)),
            Literal("x"),
            None,
            "integer Value",
        ),
    ],
)
def test_cst_031_invalid_reads_rejected(source, index, value, message) -> None:
    with pytest.raises(ConstructError, match=message):
        ListElement(source, index)


def test_cst_031_invalid_writes_rejected() -> None:
    element = ValueType(ValueKind.INTEGER)
    ref = Reference(
        Symbol("x", ValueType(ValueKind.LIST, list_type=ListType(element)), "list[int]")
    )
    with pytest.raises(ConstructError, match="type mismatch"):
        ListElementAssign(ref, Literal(0), Literal("bad"))
    with pytest.raises(ConstructError, match="integer Value"):
        ListElementAssign(ref, Literal("x"), Literal(1))
    with pytest.raises(ConstructError, match="list Reference"):
        ListElementAssign(
            Reference(Symbol("x", ValueType(ValueKind.INTEGER), "int")),
            Literal(0),
            Literal(1),
        )


def test_frt_022_list_literal_assignment_alias_and_mutation() -> None:
    program = parse("a: list[int] = [1, 2]\nb: list[int] = a\na[0] = 8\nc: int = b[0]")
    init_a, init_b, write, init_c = program.body.children
    assert isinstance(init_a, Initialize)
    assert init_a.symbol.kind is ValueKind.LIST
    assert isinstance(init_a.value, ListValue)
    assert isinstance(init_b, Initialize)
    assert isinstance(init_b.value, Reference)
    assert init_b.value.symbol is init_a.symbol
    assert isinstance(write, ListElementAssign)
    assert write.target.symbol is init_a.symbol
    assert isinstance(init_c, Initialize)
    assert isinstance(init_c.value, ListElement)
    assert init_c.value.source.symbol is init_b.symbol
    assert no_ast(program)


def test_frt_022_empty_list_is_contextually_typed() -> None:
    program = parse("a: list[int] = []\na[0] = 3")
    init = program.body.children[0]
    assert isinstance(init.value, ListValue)
    assert init.value.items == ()
    assert init.value.list_type.annotation() == "list[int]"


def test_frt_022_nested_lists_and_tuple_projections() -> None:
    program = parse(
        "a: list[list[int]] = [[], [1, 2]]\n"
        "b: list[int] = a[0]\n"
        "pair: tuple[list[int], int] = (b, 3)\n"
        "c: list[int] = pair[0]"
    )
    init = program.body.children[0]
    assert isinstance(init.value, ListValue)
    assert isinstance(init.value.items[0], ListValue)
    assert init.value.items[0].items == ()
    assert init.value.list_type.annotation() == "list[list[int]]"
    projection = program.body.children[-1].value
    assert isinstance(projection, TupleElement)
    assert projection.kind is ValueKind.LIST
    assert projection.list_type.annotation() == "list[int]"


def test_frt_022_dynamic_negative_index_and_reassignment() -> None:
    program = parse(
        "a: list[str] = ['x']\ni: int = -1\na[i] = 'y'\nx: str = a[i]\na = ['z']"
    )
    assert isinstance(program.body.children[2], ListElementAssign)
    assert isinstance(program.body.children[2].index, Reference)
    assert isinstance(program.body.children[3].value, ListElement)
    assert isinstance(program.body.children[4], Assign)
    assert program.body.children[4].value.list_type.annotation() == "list[str]"


def test_frt_022_function_argument_return_and_callable_shapes() -> None:
    program = parse(
        "from typing import Callable\n"
        "def clone(xs: list[int]) -> list[int]:\n"
        "    return xs\n"
        "callback: Callable[[list[int]], list[int]] = clone\n"
        "result: list[int] = callback([1, 2])\n"
        "another: list[int] = clone([3])"
    )
    fn = program.body.children[0]
    assert isinstance(fn, FunctionDefinition)
    assert fn.signature.parameters[0].list_type.annotation() == "list[int]"
    assert fn.signature.return_type.list_type.annotation() == "list[int]"
    assert fn.signature.callable_type.annotation() == "Callable[[list[int]], list[int]]"
    assert isinstance(program.body.children[2].value, FunctionValueCall)
    assert isinstance(program.body.children[3].value, FunctionCall)
    assert program.body.children[2].value.list_type.annotation() == "list[int]"


def test_frt_022_function_can_return_empty_typed_list() -> None:
    program = parse("def get() -> list[int]:\n    return []")
    ret = program.body.children[0].body.children[0]
    assert isinstance(ret, Return)
    assert ret.value.list_type.annotation() == "list[int]"
    assert ret.value.items == ()


def test_frt_022_list_containing_callable_is_callable_via_projection() -> None:
    program = parse(
        "from typing import Callable\n"
        "def f(x: int) -> int:\n    return x\n"
        "a: list[Callable[[int], int]] = [f]\n"
        "n: int = a[0](5)"
    )
    invocation = program.body.children[-1].value
    assert isinstance(invocation, FunctionValueCall)
    assert isinstance(invocation.callee, ListElement)
    assert invocation.callee.callable_type.annotation() == "Callable[[int], int]"
    assert invocation.kind is ValueKind.INTEGER


def test_frt_022_nested_scope_capture_for_list_read() -> None:
    program = parse(
        "def outer(xs: list[int]) -> int:\n"
        "    def inner() -> int:\n"
        "        return xs[0]\n"
        "    return inner()"
    )
    outer = program.body.children[0]
    inner = outer.body.children[0]
    assert lexical_captures(inner) == (outer.signature.parameters[0],)
    assert inner.body.children[0].value.source.symbol is outer.signature.parameters[0]


@pytest.mark.parametrize(
    "source,fragment",
    [
        ("a: list[int] = [1, 'a']", "List element type mismatch"),
        ("a: list[int] = ['a']", "List element type mismatch"),
        ("a: list[int] = [1]\na[0] = 's'", "type mismatch"),
        ("a: list[int] = [1]\na['zero'] = 1", "integer Value"),
        ("a: list[int] = [1]\na = ['a']", "List element type mismatch"),
        ("a: list[int] = [1]\nb: list[str] = a", "Annotated type does not match"),
        ("a: list[int] = []\na[0:1] = [1]", "Unsupported expression"),
        ("a: list[int] = [1]\na.append(2)", "Unregistered interface mapping object"),
        ("a: list[int] = [1]\na += [2]", "scalar int or float target"),
        ("a = []", "explicit type annotation"),
        ("a: list = []", "Unknown type annotation"),
        ("a: list[None] = []", "Unsupported list element type"),
        ("a: list[int, str] = []", "Only explicit simple"),
        ("a: list[int] = [x for x in range(3)]", "Unsupported expression"),
        ("a: tuple[int] = (1,)\na[0] = 3", "Only simple name assignments"),
    ],
)
def test_frt_023_unsupported_python_forms_fail_explicitly(
    source: str, fragment: str
) -> None:
    with pytest.raises(UnsupportedPython, match=fragment):
        parse(source)


def test_frt_023_missing_target_binding_is_explicit_no_model_mutation() -> None:
    model = parse("a: list[int] = [3, 4]\nb: int = a[0]\na[1] = 7")
    snapshot = repr(model)
    with pytest.raises(ConstructError, match="No 'c' realization for ListValue"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot
    assert no_ast(model)


def test_frt_022_contextual_empty_list_function_arguments() -> None:
    direct = parse(
        "def count(xs: list[int]) -> list[int]:\n    return xs\n"
        "a: list[int] = count([])"
    )
    value = direct.body.children[-1].value
    assert isinstance(value, FunctionCall)
    assert isinstance(value.arguments[0], ListValue)
    assert value.arguments[0].items == ()
    indirect = parse(
        "from typing import Callable\n"
        "def count(xs: list[int]) -> list[int]:\n    return xs\n"
        "f: Callable[[list[int]], list[int]] = count\n"
        "a: list[int] = f([])"
    )
    call = indirect.body.children[-1].value
    assert isinstance(call, FunctionValueCall)
    assert call.arguments[0].items == ()


def test_frt_022_nested_function_mutates_outer_list_without_rebinding() -> None:
    program = parse(
        "def outer(xs: list[int]) -> int:\n"
        "    def inner() -> int:\n"
        "        xs[0] = 7\n"
        "        return xs[0]\n"
        "    return inner()"
    )
    outer = program.body.children[0]
    inner = outer.body.children[0]
    write = inner.body.children[0]
    assert isinstance(write, ListElementAssign)
    assert write.target.symbol is outer.signature.parameters[0]
    assert lexical_captures(inner) == (outer.signature.parameters[0],)
