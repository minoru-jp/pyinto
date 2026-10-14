"""Phase 30: contextually typed anonymous functions reuse lexical function Model."""

from __future__ import annotations

import pytest

from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    Arithmetic,
    Block,
    BooleanLiteral,
    CallableType,
    ConditionalExpression,
    ConstructError,
    FunctionDefinition,
    FunctionValueCall,
    Initialize,
    LambdaValue,
    ListValue,
    Literal,
    Reference,
    Return,
    TupleValue,
    ValueKind,
    ValueType,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def body(source: str):
    return PythonFrontend().parse(source).body.children


def test_basic_lambda_is_first_class_typed_expression() -> None:
    initialize, call = body(
        "from typing import Callable\n"
        "fn: Callable[[int], int] = lambda x: x + 1\n"
        "result: int = fn(4)\n"
    )
    assert isinstance(initialize, Initialize)
    expr = initialize.value
    assert isinstance(expr, LambdaValue)
    assert expr.kind is ValueKind.FUNCTION
    assert expr.callable_type == initialize.symbol.callable_type
    assert isinstance(expr.definition, FunctionDefinition)
    assert expr.definition.signature.parameters[0].name == "x"
    assert isinstance(expr.definition.body.children[0], Return)
    result = expr.definition.body.children[0].value
    assert isinstance(result, Arithmetic)
    assert isinstance(result.left, Reference)
    assert result.left.symbol is expr.definition.signature.parameters[0]
    assert expr.parts() == {"definition": expr.definition}
    assert isinstance(call.value, FunctionValueCall)


def test_lambda_without_parameters_and_boolean_value() -> None:
    expr = body("from typing import Callable\nf: Callable[[], bool] = lambda: True\n")[
        0
    ].value
    assert isinstance(expr, LambdaValue)
    assert expr.definition.signature.parameters == ()
    assert isinstance(expr.definition.body.children[0].value, BooleanLiteral)


def test_lambda_none_return_and_nested_callable() -> None:
    expr = body(
        "from typing import Callable\n"
        "fn: Callable[[int], Callable[[], int]] = lambda x: lambda: x\n"
    )[0].value
    assert isinstance(expr, LambdaValue)
    nested = expr.definition.body.children[0].value
    assert isinstance(nested, LambdaValue)
    assert nested.definition.signature.scope == (expr.definition.signature.name,)
    assert lexical_captures(nested.definition) == (
        expr.definition.signature.parameters[0],
    )
    none_expr = body(
        "from typing import Callable\nf: Callable[[], None] = lambda: None\n"
    )[0].value
    assert isinstance(none_expr, LambdaValue)
    assert none_expr.definition.signature.return_type.kind is ValueKind.NONE


def test_lambda_capture_outer_parameter_with_escaped_value() -> None:
    function = body("""
from typing import Callable
def maker(x: int) -> Callable[[int], int]:
    return lambda y: x + y
""")[0]
    assert isinstance(function, FunctionDefinition)
    lam = function.body.children[0].value
    assert isinstance(lam, LambdaValue)
    assert lexical_captures(lam.definition) == (function.signature.parameters[0],)
    assert lexical_captures(function) == ()
    assert lam.definition.signature.scope == ("maker",)


def test_distinct_lambda_values_have_distinct_lexical_declarations() -> None:
    function = body("""
from typing import Callable
def factory(x: int) -> tuple[Callable[[], int], Callable[[], int]]:
    a: Callable[[], int] = lambda: x
    b: Callable[[], int] = lambda: x
    return (a, b)
""")[0]
    lam_a = function.body.children[0].value
    lam_b = function.body.children[1].value
    assert isinstance(lam_a, LambdaValue) and isinstance(lam_b, LambdaValue)
    assert lam_a.definition.signature.name != lam_b.definition.signature.name
    assert lexical_captures(lam_a.definition) == (function.signature.parameters[0],)
    assert lexical_captures(lam_b.definition) == (function.signature.parameters[0],)


def test_lambda_as_typed_direct_call_argument_and_indirect_call_argument() -> None:
    function, assignment = body("""
from typing import Callable
def apply(fn: Callable[[int], int], v: int) -> int:
    return fn(v)
result: int = apply(lambda x: x + 2, 3)
""")
    assert isinstance(function, FunctionDefinition)
    assert isinstance(assignment.value.arguments[0], LambdaValue)
    _, assignment = body("""
from typing import Callable
def apply(fn: Callable[[int], int], v: int) -> int:
    return fn(v)
fn: Callable[[Callable[[int], int], int], int] = apply
r: int = fn(lambda x: x + 2, 3)
""")[1:]
    assert isinstance(assignment.value, FunctionValueCall)
    assert isinstance(assignment.value.arguments[0], LambdaValue)


def test_lambda_inside_typed_list_tuple_and_condition() -> None:
    values = body("""
from typing import Callable
fs: list[Callable[[int], int]] = [lambda x: x + 1, lambda x: x * 2]
""")[0].value
    assert isinstance(values, ListValue)
    assert all(isinstance(item, LambdaValue) for item in values.items)
    pair = body("""
from typing import Callable
fs: tuple[Callable[[], bool], Callable[[int], int]] = (lambda: True, lambda x: x)
""")[0].value
    assert isinstance(pair, TupleValue)
    assert all(isinstance(item, LambdaValue) for item in pair.items)
    conditional = body("""
from typing import Callable
flag: bool = True
fn: Callable[[int], int] = (lambda x: x + 1) if flag else (lambda x: x - 1)
""")[1].value
    assert isinstance(conditional, ConditionalExpression)
    assert isinstance(conditional.when_true, LambdaValue)
    assert isinstance(conditional.when_false, LambdaValue)


def test_lambda_captures_outer_function_reference_without_special_closure_node() -> (
    None
):
    outer = body("""
from typing import Callable
def make(n: int) -> Callable[[int], int]:
    def add(x: int) -> int:
        return n + x
    return lambda value: add(value)
""")[0]
    lam = outer.body.children[1].value
    assert isinstance(lam, LambdaValue)
    inner_decl = outer.body.children[0]
    assert lexical_captures(lam.definition) == (inner_decl.signature.value_symbol,)


def test_lambda_owner_scope_deterministic_and_frontend_reusable() -> None:
    src = "from typing import Callable\nf: Callable[[int], int] = lambda x: x\n"
    parser = PythonFrontend()
    first = parser.parse(src).body.children[0].value
    second = parser.parse(src).body.children[0].value
    assert first == second
    assert first.definition.signature.name == second.definition.signature.name


def test_synthetic_lambda_name_cannot_collide_with_future_source_declaration() -> None:
    source = """
from typing import Callable
f: Callable[[], int] = lambda: 1
__henkan_lambda_1: int = 3
"""
    items = body(source)
    assert isinstance(items[0].value, LambdaValue)
    assert items[0].value.definition.signature.name != "__henkan_lambda_1"
    assert items[1].symbol.name == "__henkan_lambda_1"


def test_direct_model_validation_and_function_kind() -> None:
    lam = body("from typing import Callable\nf: Callable[[], int] = lambda: 2\n")[
        0
    ].value
    assert isinstance(lam, LambdaValue)
    assert isinstance(lam.definition.body.children[0].value, Literal)
    sig = lam.definition.signature
    with pytest.raises(ConstructError, match="single return"):
        LambdaValue(FunctionDefinition(sig, Block(())))
    with pytest.raises(ConstructError, match="return type mismatch"):
        LambdaValue(FunctionDefinition(sig, Block((Return(BooleanLiteral(True)),))))
    assert ValueType(ValueKind.FUNCTION, lam.callable_type) == lam.value_type
    assert isinstance(lam.callable_type, CallableType)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("f: object = lambda x: x", "explicit Callable"),
        ("f: Callable[[int], int] = lambda x, y: x", "matching Callable"),
        ("f: Callable[[int], int] = lambda: 1", "matching Callable"),
        ("f: Callable[[int], int] = lambda x=1: x", "matching Callable"),
        ("f: Callable[[int], int] = lambda *xs: 1", "matching Callable"),
        ("f: Callable[[int], int] = lambda **kw: 1", "matching Callable"),
        ("f: Callable[[int], int] = lambda x, /: x", "matching Callable"),
        ("f: Callable[[int], int] = lambda *, x: x", "matching Callable"),
        ('f: Callable[[int], int] = lambda x: "text"', "body type"),
        ("f: Callable[[], int] = lambda: None", "body type"),
        ("f: Callable[[], None] = lambda: 5", "must yield None"),
        ("f: Callable[[int], int] = lambda x: other", "Unresolved name"),
    ],
)
def test_lambda_rejects_unsupported_forms(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend().parse("from typing import Callable\n" + source)


def test_lambda_with_no_context_is_rejected() -> None:
    with pytest.raises(UnsupportedPython, match="explicit Callable"):
        body(
            "from typing import Callable\nf: Callable[[], int] = lambda: (lambda x: x)\n"
        )


def test_lambda_realization_without_binding_fails_explicitly() -> None:
    from pyinto.api import realize
    from tests.support.c_realizer import c_bindings

    program = PythonFrontend().parse(
        "from typing import Callable\nf: Callable[[], int] = lambda: 3\n"
    )
    with pytest.raises(ConstructError, match="[Uu]nregistered|[Mm]issing|[Nn]o "):
        realize(program, realizations=c_bindings())
