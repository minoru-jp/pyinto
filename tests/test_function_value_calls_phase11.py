"""SDD phase 11: call typed function Values without changing direct FunctionCall."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    CallableType,
    ConstructError,
    ExpressionStatement,
    FunctionCall,
    FunctionValueCall,
    Initialize,
    Literal,
    Reference,
    Return,
    Symbol,
    Value,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def _value_type(kind: ValueKind) -> ValueType:
    return ValueType(kind)


def _symbol(name: str, shape: CallableType) -> Symbol:
    return Symbol(
        name, ValueType(ValueKind.FUNCTION, callable_type=shape), shape.annotation()
    )


def _has_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_ast(v) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_has_ast(getattr(value, f.name)) for f in fields(value))
    return False


def test_cst_022_value_call_has_value_callee_and_numbered_children() -> None:
    shape = CallableType(
        (_value_type(ValueKind.INTEGER),), _value_type(ValueKind.STRING)
    )
    callee = Reference(_symbol("f", shape))
    argument = Literal(7)
    call = FunctionValueCall(callee, (argument,))
    assert call.kind is ValueKind.STRING
    assert call.callable_type is None
    assert call.callee is callee
    assert call.parts() == {"callee": callee, "arg0": argument}
    assert call.parts()["callee"] is callee
    assert not _has_ast(call)
    for part in ("callee", "arg0", "arg12"):
        assert FunctionValueCall.accepts_part_name(part)
    for part in ("arg", "arg01", "arg-1", "arg０", "other", "body"):
        assert not FunctionValueCall.accepts_part_name(part)


def test_cst_022_empty_argument_call_and_none_result() -> None:
    shape = CallableType((), _value_type(ValueKind.NONE))
    call = FunctionValueCall(Reference(_symbol("unit", shape)), ())
    assert call.kind is ValueKind.NONE
    assert call.parts() == {"callee": call.callee}
    assert call.callable_type is None


def test_cst_022_recursive_callable_return_type_is_preserved() -> None:
    result = CallableType(
        (_value_type(ValueKind.STRING),), _value_type(ValueKind.INTEGER)
    )
    outer = CallableType((), ValueType(ValueKind.FUNCTION, result))
    inner_call = FunctionValueCall(Reference(_symbol("f", outer)), ())
    assert inner_call.kind is ValueKind.FUNCTION
    assert inner_call.callable_type == result
    result_call = FunctionValueCall(inner_call, (Literal("hello"),))
    assert result_call.callee is inner_call
    assert result_call.kind is ValueKind.INTEGER
    assert result_call.parts()["arg0"] == Literal("hello")


@pytest.mark.parametrize(
    ("callee", "arguments", "error"),
    [
        (Literal(1), (), "must be a function"),
        ("wrong", (), "must be a Value"),
        (
            Reference(
                _symbol(
                    "f",
                    CallableType(
                        (_value_type(ValueKind.INTEGER),),
                        _value_type(ValueKind.INTEGER),
                    ),
                )
            ),
            (),
            "count mismatch",
        ),
        (
            Reference(
                _symbol(
                    "f",
                    CallableType(
                        (_value_type(ValueKind.INTEGER),),
                        _value_type(ValueKind.INTEGER),
                    ),
                )
            ),
            (Literal("x"),),
            "type mismatch",
        ),
        (
            Reference(
                _symbol(
                    "f",
                    CallableType(
                        (_value_type(ValueKind.INTEGER),),
                        _value_type(ValueKind.INTEGER),
                    ),
                )
            ),
            ("bad",),
            "must be Values",
        ),
    ],
)
def test_cst_022_rejects_invalid_calleepath_and_arguments(
    callee: Value, arguments: tuple[Value, ...], error: str
) -> None:
    with pytest.raises(ConstructError, match=error):
        FunctionValueCall(callee, arguments)


def test_cst_022_callable_argument_requires_exact_nested_shape() -> None:
    inner = CallableType(
        (_value_type(ValueKind.INTEGER),), _value_type(ValueKind.INTEGER)
    )
    other = CallableType(
        (_value_type(ValueKind.STRING),), _value_type(ValueKind.INTEGER)
    )
    outer = CallableType(
        (ValueType(ValueKind.FUNCTION, inner),), _value_type(ValueKind.NONE)
    )
    good = FunctionValueCall(
        Reference(_symbol("consumer", outer)), (Reference(_symbol("g", inner)),)
    )
    assert good.kind is ValueKind.NONE
    with pytest.raises(ConstructError, match="type mismatch"):
        FunctionValueCall(
            Reference(_symbol("consumer", outer)), (Reference(_symbol("h", other)),)
        )


def test_cst_022_any_and_object_parameter_types_are_intentionally_permissive() -> None:
    for kind in (ValueKind.ANY, ValueKind.OBJECT):
        signature = CallableType((_value_type(kind),), _value_type(ValueKind.NONE))
        assert (
            FunctionValueCall(Reference(_symbol("any", signature)), (Literal(11),)).kind
            is ValueKind.NONE
        )


def test_frt_015_direct_and_indirect_calls_remain_distinct() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def inc(n: int) -> int:\n    return n + 1\n"
        "def apply(fn: Callable[[int], int], x: int) -> int:\n    return fn(x)\n"
        "f: Callable[[int], int] = inc\n"
        "a: int = inc(1)\n"
        "b: int = f(2)\n"
        "c: int = apply(f, 3)\n"
    )
    inc, apply, binding, a, b, c = program.body.children
    assert isinstance(a, Initialize) and isinstance(a.value, FunctionCall)
    assert a.value.signature is inc.signature
    assert isinstance(b.value, FunctionValueCall)
    assert b.value.callee.symbol is binding.symbol
    assert b.value.kind is ValueKind.INTEGER
    assert isinstance(c.value, FunctionCall)
    returned = apply.body.children[0]
    assert isinstance(returned, Return)
    assert isinstance(returned.value, FunctionValueCall)
    assert isinstance(returned.value.callee, Reference)
    assert returned.value.callee.symbol is apply.signature.parameters[0]
    assert returned.value.arguments[0].symbol is apply.signature.parameters[1]
    assert not _has_ast(program)


def test_frt_015_function_value_calls_in_statements_and_none() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def report(n: int) -> None:\n    print('msg')\n    return\n"
        "def use(fn: Callable[[int], None]) -> None:\n    fn(10)\n    return\n"
        "cb: Callable[[int], None] = report\n"
        "cb(3)\n"
        "use(cb)\n"
    )
    _, use, _, expr, direct = program.body.children
    assert isinstance(expr, ExpressionStatement)
    assert isinstance(expr.value, FunctionValueCall)
    assert expr.value.kind is ValueKind.NONE
    assert isinstance(direct.value, FunctionCall)
    inside = use.body.children[0]
    assert isinstance(inside, ExpressionStatement)
    assert isinstance(inside.value, FunctionValueCall)


def test_frt_015_factory_return_call_callee_is_a_structural_expression() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def make(x: int) -> Callable[[int], int]:\n"
        "    def add(y: int) -> int:\n        return x + y\n"
        "    return add\n"
        "n: int = make(5)(7)\n"
    )
    make, n = program.body.children
    assert isinstance(n.value, FunctionValueCall)
    assert isinstance(n.value.callee, FunctionCall)
    assert n.value.callee.signature is make.signature
    assert n.value.parts()["callee"] is n.value.callee
    nested, _ = make.body.children
    captured = nested.body.children[0].value.left
    assert captured.symbol is make.signature.parameters[0]


def test_frt_015_callable_return_from_indirect_call_is_another_callable() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def get_factory(fn: Callable[[], Callable[[str], int]]) -> int:\n"
        "    produced: Callable[[str], int] = fn()\n"
        "    return produced('abc')\n"
    )
    outer = program.body.children[0]
    produced, returned = outer.body.children
    assert isinstance(produced.value, FunctionValueCall)
    assert produced.value.kind is ValueKind.FUNCTION
    assert produced.value.callable_type == produced.symbol.callable_type
    assert isinstance(returned.value, FunctionValueCall)
    assert returned.value.callee.symbol is produced.symbol


def test_frt_015_returned_closure_calls_preserve_static_capture_routes() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def factory(x: int) -> Callable[[], int]:\n"
        "    def get() -> int:\n        return x\n"
        "    return get\n"
        "a: Callable[[], int] = factory(1)\n"
        "b: Callable[[], int] = factory(2)\n"
        "r: int = a()\n"
        "s: int = b()\n"
    )
    factory, a, b, r, s = program.body.children
    nested = factory.body.children[0]
    assert nested.body.children[0].value.symbol is factory.signature.parameters[0]
    assert a.value.signature is factory.signature
    assert b.value.signature is factory.signature
    assert r.value.callee.symbol is a.symbol
    assert s.value.callee.symbol is b.symbol
    assert r.value.kind is s.value.kind is ValueKind.INTEGER


def test_frt_015_function_value_scope_is_lexically_resolved() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def outer(f: Callable[[int], int]) -> int:\n"
        "    def inner(x: int) -> int:\n        return f(x)\n"
        "    return inner(1)\n"
    )
    outer = program.body.children[0]
    inner, returned = outer.body.children
    inner_return = inner.body.children[0]
    assert inner_return.value.callee.symbol is outer.signature.parameters[0]
    assert isinstance(returned.value, FunctionCall)


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (
            (
                "from typing import Callable\n"
                "def fn(f: Callable[[int], int]) -> int:\n    return f()\n"
            ),
            "argument count mismatch",
        ),
        (
            (
                "from typing import Callable\n"
                "def fn(f: Callable[[int], int]) -> int:\n    return f('bad')\n"
            ),
            "argument type mismatch",
        ),
        (
            (
                "from typing import Callable\n"
                "def fn(f: Callable[[int], int]) -> int:\n    return f(x=1)\n"
            ),
            "positional arguments only",
        ),
        (
            (
                "from typing import Callable\n"
                "def fn(f: Callable[[int], int]) -> int:\n    return f(1, 2)\n"
            ),
            "argument count mismatch",
        ),
        (
            (
                "from typing import Callable\n"
                "def fn(f: Callable[[int], int]) -> int:\n    return f(*(1,))\n"
            ),
            "Unsupported expression",
        ),
        (
            (
                "from typing import Callable\n"
                "def make() -> Callable[[int], int]:\n"
                "    def f(n: int) -> int:\n        return n\n"
                "    return f\n"
                "make()(n=3)\n"
            ),
            "positional arguments only",
        ),
        (
            "def n() -> int:\n    return 1\nn()()\n",
            "must be a function",
        ),
        (
            (
                "from typing import Callable\n"
                "def fn(f: Callable[[int], None]) -> int:\n    return f(1)\n"
            ),
            "Return type mismatch",
        ),
    ],
)
def test_frt_016_invalid_indirect_calls_are_rejected(source: str, reason: str) -> None:
    with pytest.raises(UnsupportedPython, match=reason):
        PythonFrontend().parse(source)


def test_frt_016_no_realization_is_expressly_rejected() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def inc(n: int) -> int:\n    return n\n"
        "f: Callable[[int], int] = inc\n"
        "result: int = f(4)\n"
    )
    with pytest.raises(ConstructError, match="[Uu]nregistered|[Mm]issing|[Nn]o "):
        realize(program, realizations=c_bindings())


def test_frt_016_unsupported_python_dynamic_function_forms_are_unchanged() -> None:
    for source in (
        (
            "from typing import Callable\n"
            "def f(fn: Callable[[int], int]) -> int:\n    return fn.__call__(3)\n"
        ),
        (
            "from typing import Callable\n"
            "def f(fn: Callable[[int], int]) -> int:\n"
            "    return (lambda n: n)(1)\n"
        ),
    ):
        with pytest.raises(UnsupportedPython):
            PythonFrontend().parse(source)
