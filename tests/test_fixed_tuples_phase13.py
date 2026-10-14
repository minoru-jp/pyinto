"""SDD phase 13: fixed-size tuple values and structural indexing (Model only)."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Assign,
    CallableType,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    FunctionValueCall,
    Initialize,
    Literal,
    Reference,
    Return,
    Symbol,
    TupleElement,
    TupleType,
    TupleValue,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def _contains_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_ast(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_contains_ast(getattr(value, field.name)) for field in fields(value))
    return False


def _shape(*kinds: ValueKind) -> TupleType:
    return TupleType(tuple(ValueType(kind) for kind in kinds))


def test_cst_025_tuple_type_is_immutable_recursive_structural_data() -> None:
    integer = ValueType(ValueKind.INTEGER)
    shape = TupleType((integer, ValueType(ValueKind.STRING)))
    nested = TupleType((ValueType(ValueKind.TUPLE, tuple_type=shape), integer))
    assert shape.annotation() == "tuple[int, str]"
    assert nested.annotation() == "tuple[tuple[int, str], int]"
    assert TupleType(()).annotation() == "tuple[()]"
    assert (
        ValueType(ValueKind.TUPLE, tuple_type=nested).annotation()
        == nested.annotation()
    )
    assert shape == _shape(ValueKind.INTEGER, ValueKind.STRING)
    assert shape != _shape(ValueKind.STRING, ValueKind.INTEGER)
    assert not _contains_ast(nested)


def test_cst_025_tuple_shape_is_mandatory_only_for_tuple_kind() -> None:
    shape = _shape(ValueKind.INTEGER)
    with pytest.raises(ConstructError, match="tuple shape"):
        ValueType(ValueKind.TUPLE)
    with pytest.raises(ConstructError, match="tuple shape"):
        ValueType(ValueKind.INTEGER, tuple_type=shape)
    with pytest.raises(ValueError, match="tuple shape"):
        Symbol("pair", ValueType(ValueKind.TUPLE), "tuple[int]")
    with pytest.raises(ValueError, match="tuple shape"):
        Symbol("int_var", ValueType(ValueKind.INTEGER, tuple_type=shape), "int")
    with pytest.raises(ConstructError, match="supported value types"):
        TupleType((ValueType(ValueKind.NONE),))
    with pytest.raises(ConstructError, match="valid value types"):
        TupleType(("wrong",))  # type: ignore[arg-type]


def test_cst_025_tuple_value_keeps_source_order_and_nested_types() -> None:
    nested = TupleValue((Literal("z"),))
    tuple_value = TupleValue((Literal(3), nested, Literal("a")))
    assert tuple_value.kind is ValueKind.TUPLE
    assert tuple_value.tuple_type == TupleType(
        (
            ValueType(ValueKind.INTEGER),
            ValueType(ValueKind.TUPLE, tuple_type=nested.tuple_type),
            ValueType(ValueKind.STRING),
        )
    )
    assert tuple_value.parts()["items"] == tuple_value.items
    assert tuple_value.items[1] is nested
    assert tuple_value.HOLES == frozenset({"items"})
    assert TupleValue(()).tuple_type == TupleType(())
    with pytest.raises(ConstructError, match="must be Values"):
        TupleValue(("bad",))  # type: ignore[arg-type]


def test_cst_026_fixed_tuple_element_infers_precise_type() -> None:
    item = TupleValue((Literal(5), Literal("s")))
    projected = TupleElement(item, 1)
    assert projected.kind is ValueKind.STRING
    assert projected.parts() == {"source": item, "index": Literal(1)}
    assert projected.parts()["source"] is item
    assert projected.HOLES == frozenset({"source", "index"})
    assert TupleElement(item, 0).kind is ValueKind.INTEGER


def test_cst_026_tuple_projection_preserves_nested_callable_type() -> None:
    fn = CallableType((ValueType(ValueKind.INTEGER),), ValueType(ValueKind.STRING))
    symbol = Symbol(
        "f", ValueType(ValueKind.FUNCTION, callable_type=fn), fn.annotation()
    )
    item = TupleValue((Literal(7), Reference(symbol)))
    projected = TupleElement(item, 1)
    assert projected.kind is ValueKind.FUNCTION
    assert projected.callable_type == fn
    assert projected.tuple_type is None
    assert FunctionValueCall(projected, (Literal(3),)).kind is ValueKind.STRING


def test_cst_026_tuple_element_propagates_nested_tuple_shape() -> None:
    item = TupleValue((TupleValue((Literal(4), Literal("x"))), Literal(1)))
    nested = TupleElement(item, 0)
    assert nested.kind is ValueKind.TUPLE
    assert nested.tuple_type == _shape(ValueKind.INTEGER, ValueKind.STRING)
    assert TupleElement(nested, 1).kind is ValueKind.STRING


@pytest.mark.parametrize("bad_index", [-1, 2, True, "0", 0.0])
def test_cst_026_tuple_rejects_invalid_static_index(bad_index: object) -> None:
    with pytest.raises(ConstructError, match="static position"):
        TupleElement(TupleValue((Literal(1), Literal(2))), bad_index)  # type: ignore[arg-type]


def test_cst_026_non_tuple_indexing_is_rejected() -> None:
    with pytest.raises(ConstructError, match="requires a tuple"):
        TupleElement(Literal(1), 0)
    with pytest.raises(ConstructError, match="static position"):
        TupleElement(TupleValue(()), 0)


def test_cst_025_tuple_initialization_and_assignment_enforce_shape() -> None:
    sym = Symbol(
        "pair",
        ValueType(
            ValueKind.TUPLE, tuple_type=_shape(ValueKind.INTEGER, ValueKind.STRING)
        ),
        "tuple[int, str]",
    )
    good = TupleValue((Literal(1), Literal("abc")))
    bad = TupleValue((Literal("abc"), Literal(1)))
    assert Initialize(sym, good).value is good
    assert Assign(Reference(sym), good).value is good
    with pytest.raises(ConstructError, match="type mismatch"):
        Initialize(sym, bad)
    with pytest.raises(ConstructError, match="type mismatch"):
        Assign(Reference(sym), bad)


def test_frt_018_typed_tuple_literal_assignment_and_projection() -> None:
    program = PythonFrontend().parse(
        'pair: tuple[int, str] = (2, "a")\n'
        'pair = (3, "b")\n'
        "first: int = pair[0]\n"
        "second: str = pair[1]\n"
    )
    initial, reassignment, first, second = program.body.children
    assert isinstance(initial, Initialize)
    assert initial.symbol.tuple_type == _shape(ValueKind.INTEGER, ValueKind.STRING)
    assert isinstance(initial.value, TupleValue)
    assert isinstance(reassignment, Assign)
    assert isinstance(reassignment.value, TupleValue)
    assert isinstance(first, Initialize)
    assert isinstance(first.value, TupleElement)
    assert first.value.source.symbol is initial.symbol
    assert isinstance(second.value, TupleElement)
    assert second.value.index == 1
    assert not _contains_ast(program)


def test_frt_018_nested_and_empty_tuple_shapes() -> None:
    program = PythonFrontend().parse(
        "empty: tuple[()] = ()\n"
        'nested: tuple[tuple[int, str], int] = ((1, "a"), 5)\n'
        "text: str = nested[0][1]\n"
    )
    empty, nested, text = program.body.children
    assert empty.value.tuple_type == TupleType(())
    assert nested.symbol.tuple_type is not None
    assert nested.symbol.tuple_type.annotation() == "tuple[tuple[int, str], int]"
    assert isinstance(text.value, TupleElement)
    assert isinstance(text.value.source, TupleElement)
    assert text.value.kind is ValueKind.STRING


def test_frt_018_direct_call_return_and_parameter_structural_tuples() -> None:
    program = PythonFrontend().parse(
        "def swap(pair: tuple[int, str]) -> tuple[str, int]:\n"
        "    return (pair[1], pair[0])\n"
        'result: tuple[str, int] = swap((3, "x"))\n'
        "word: str = result[0]\n"
    )
    definition, result, word = program.body.children
    assert isinstance(definition, FunctionDefinition)
    assert definition.signature.parameters[0].tuple_type is not None
    assert definition.signature.return_type.tuple_type is not None
    assert isinstance(definition.body.children[0], Return)
    assert isinstance(result.value, FunctionCall)
    assert result.value.tuple_type == _shape(ValueKind.STRING, ValueKind.INTEGER)
    assert isinstance(word.value, TupleElement)
    assert word.value.source.symbol is result.symbol
    assert not _contains_ast(program)


def test_frt_018_callable_with_tuple_parameter_and_return() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def pair(x: tuple[int, str]) -> tuple[int, str]:\n"
        "    return x\n"
        "f: Callable[[tuple[int, str]], tuple[int, str]] = pair\n"
        'v: tuple[int, str] = f((8, "ok"))\n'
        "integer: int = v[0]\n"
    )
    _, f, v, integer = program.body.children
    assert f.symbol.callable_type is not None
    assert f.symbol.callable_type.annotation() == (
        "Callable[[tuple[int, str]], tuple[int, str]]"
    )
    assert isinstance(v.value, FunctionValueCall)
    assert v.value.tuple_type == _shape(ValueKind.INTEGER, ValueKind.STRING)
    assert isinstance(integer.value, TupleElement)


def test_frt_018_function_returning_tuple_of_functions() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def inc(x: int) -> int:\n    return x + 1\n"
        "def provider() -> tuple[Callable[[int], int], str]:\n"
        '    return (inc, "done")\n'
        "n: int = provider()[0](3)\n"
    )
    _, provider, result = program.body.children
    returned = provider.body.children[0]
    assert isinstance(returned.value, TupleValue)
    assert isinstance(result.value, FunctionValueCall)
    assert isinstance(result.value.callee, TupleElement)
    assert isinstance(result.value.callee.source, FunctionCall)
    assert result.value.kind is ValueKind.INTEGER


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("pair: tuple[int, str] = (1, 2)", "Annotated type does not match initializer"),
        ('pair: tuple[int] = (1, "x")', "Annotated type does not match initializer"),
        (
            'pair: tuple[int, str] = (1, "a")\npair = ("x", 1)',
            "Variable type cannot change",
        ),
        ('def f() -> tuple[int]:\n    return ("x",)', "Return type mismatch"),
        (
            'def f(t: tuple[int]) -> int:\n    return 1\nf(("a",))',
            "Function argument type mismatch",
        ),
        ("pair: tuple[int] = (1,)\nv: int = pair[1]", "valid static position"),
        ("pair: tuple[int] = (1,)\nv: int = pair[-1]", "nonnegative static integer"),
        (
            "pair: tuple[int] = (1,)\ni: int = 0\nv: int = pair[i]",
            "nonnegative static integer",
        ),
        ("n: int = 1\nv: int = n[0]", "requires a tuple"),
        (
            "p: tuple[int, ...] = (1, 'wrong')",
            "Annotated type does not match initializer",
        ),
        ("p: tuple[int, None] = (1, 2)", "Unsupported tuple element type"),
        ("p: tuple[()] = (1,)", "Annotated type does not match initializer"),
        ("p: tuple[int] = [1]", "Unsupported expression"),
        ("a, b = (1, 2)", "Unpack assignment requires declared targets"),
        ("p: tuple[int] = (1,)\np[0] = 2", "Only simple name assignments"),
    ],
)
def test_frt_019_rejects_unsupported_tuple_forms(source: str, fragment: str) -> None:
    with pytest.raises(UnsupportedPython, match=fragment) as exc:
        PythonFrontend().parse(source)
    assert "line " in str(exc.value)


def test_frt_019_no_extra_target_realization_and_no_model_mutation() -> None:
    model = PythonFrontend().parse('pair: tuple[int, str] = (1, "a")')
    snapshot = repr(model)
    with pytest.raises(ConstructError, match="No 'c' realization for TupleValue"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot
    assert PythonFrontend().parse('pair: tuple[int, str] = (1, "a")') == model
    assert not _contains_ast(model)


def test_frt_018_nested_function_captures_tuple_reference_without_new_closure_model() -> (
    None
):
    from pyinto.analysis import lexical_captures

    program = PythonFrontend().parse(
        "def outer(t: tuple[int, str]) -> int:\n"
        "    def read() -> int:\n"
        "        return t[0]\n"
        "    return read()\n"
    )
    outer = program.body.children[0]
    inner = outer.body.children[0]
    assert lexical_captures(inner) == (outer.signature.parameters[0],)
    assert isinstance(inner.body.children[0].value, TupleElement)
    assert inner.body.children[0].value.source.symbol is outer.signature.parameters[0]


def test_cst_026_tuple_projection_does_not_evaluate_original_expression() -> None:
    program = PythonFrontend().parse(
        "def identity(t: tuple[int, str]) -> tuple[int, str]:\n"
        "    return t\n"
        'result: int = identity((1, "two"))[0]\n'
    )
    projection = program.body.children[1].value
    assert isinstance(projection, TupleElement)
    assert isinstance(projection.source, FunctionCall)
    assert projection.parts()["source"] is projection.source
    assert projection.kind is ValueKind.INTEGER
