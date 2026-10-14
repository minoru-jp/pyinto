"""Regression checks for single-pass receiver normalization and callable scopes."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    FieldRead,
    FieldWrite,
    FunctionDefinition,
    FunctionSignature,
    FunctionValueCall,
    LambdaValue,
    MethodCall,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.frontend.context import ParseContext

HEADER = """
from typing import Callable

class A:
    def __init__(self) -> None:
        self.x: int = 1

    def get(self) -> int:
        return self.x

class Wrapper:
    def __init__(self, item: A) -> None:
        self.item: A = item


def maker(callback: Callable[[int], int]) -> Wrapper:
    return Wrapper(A())
"""


def test_field_read_normalizes_lambda_receiver_once() -> None:
    frontend = PythonFrontend()
    program = frontend.parse(HEADER + "result: A = maker(lambda i: i).item\n")
    value = program.body.children[-1].value
    assert isinstance(value, FieldRead)
    assert value.receiver.kind is ValueKind.INSTANCE
    assert frontend._context.flow.lambda_counter == 1


def test_nested_field_method_normalizes_lambda_receiver_once() -> None:
    frontend = PythonFrontend()
    program = frontend.parse(HEADER + "result: int = maker(lambda i: i).item.get()\n")
    call = program.body.children[-1].value
    assert isinstance(call, MethodCall)
    assert isinstance(call.receiver, FieldRead)
    assert frontend._context.flow.lambda_counter == 1


def test_method_statement_normalizes_lambda_receiver_once() -> None:
    frontend = PythonFrontend()
    frontend.parse(HEADER + "maker(lambda i: i).item.get()\n")
    assert frontend._context.flow.lambda_counter == 1


def test_field_write_normalizes_lambda_receiver_once() -> None:
    frontend = PythonFrontend()
    program = frontend.parse(HEADER + "maker(lambda i: i).item.x = 3\n")
    statement = program.body.children[-1]
    assert isinstance(statement, FieldWrite)
    assert frontend._context.flow.lambda_counter == 1


def test_callable_scope_restores_state_after_nested_exception() -> None:
    context = ParseContext()
    outer = Symbol("a", ValueType(ValueKind.INTEGER), "int")
    context.names.symbols["a"] = outer
    context.names.functions["top"] = FunctionSignature(
        "top", (), "int", ValueType(ValueKind.INTEGER)
    )
    context.names.local_names.add("a")
    context.names.function_body_depth = 2
    context.classes.initialized_fields.add("field")
    context.classes.collecting_methods = True
    context.flow.loop_depth = 4
    original_symbols = context.names.symbols
    original_functions = context.names.functions
    original_fields = context.classes.initialized_fields
    signature = FunctionSignature("nested", (), "int", ValueType(ValueKind.INTEGER))
    with pytest.raises(RuntimeError, match="error inside lambda"):  # noqa: SIM117
        with context.callable_scope(
            signature,
            local_names={"inner"},
            function_body_depth=3,
            reset_method_state=True,
        ):
            assert context.names.local_names == {"inner"}
            assert context.names.enclosing_scopes
            assert context.flow.loop_depth == 0
            assert context.classes.initialized_fields == set()
            with context.callable_scope(
                signature, local_names=set(), function_body_depth=None
            ):
                assert len(context.names.enclosing_scopes) == 2
                raise RuntimeError("error inside lambda")
    assert context.names.symbols is original_symbols
    assert context.names.functions is original_functions
    assert context.names.active_function is None
    assert context.names.enclosing_scopes == []
    assert context.names.local_names == {"a"}
    assert context.names.function_body_depth == 2
    assert context.flow.loop_depth == 4
    assert context.classes.collecting_methods is True
    assert context.classes.initialized_fields is original_fields
    assert context.classes.initialized_fields == {"field"}


def test_failed_lambda_does_not_leave_lexical_scope_active() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython, match="Lambda body type"):
        frontend.parse(
            "from typing import Callable\n"
            "def wrapper() -> Callable[[int], int]:\n"
            "    return lambda x: 'bad'\n"
        )
    assert frontend._context.names.enclosing_scopes == []
    assert frontend._context.names.active_function is None
    assert frontend._context.names.function_body_depth is None
    assert frontend._context.flow.loop_depth == 0
    # Failure recovery must also leave the configured frontend reusable.
    good = frontend.parse(
        "from typing import Callable\nf: Callable[[int], int] = lambda x: x\n"
    )
    assert isinstance(good.body.children[0].value, LambdaValue)


def test_failed_nested_function_restores_parent_state() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython):
        frontend.parse(
            "def outer(x: int) -> int:\n"
            "    def inner(y: int) -> int:\n"
            "        return unknown\n"
            "    return x\n"
        )
    assert frontend._context.names.enclosing_scopes == []
    assert frontend._context.names.active_function is None
    assert frontend._context.classes.method_owner is None
    assert frontend._context.names.function_body_depth is None
    good = frontend.parse("def f(x: int) -> int:\n    return x\n")
    assert isinstance(good.body.children[0], FunctionDefinition)


def test_callable_field_call_does_not_recreate_receiver_lambda() -> None:
    frontend = PythonFrontend()
    program = frontend.parse(
        "from typing import Callable\n"
        "class Handler:\n"
        "    def __init__(self, callback: Callable[[int], int]) -> None:\n"
        "        self.callback: Callable[[int], int] = callback\n"
        "def make(callback: Callable[[int], int]) -> Handler:\n"
        "    return Handler(callback)\n"
        "result: int = make(lambda x: x).callback(3)\n"
    )
    assert isinstance(program.body.children[-1].value, FunctionValueCall)
    assert isinstance(program.body.children[-1].value.callee, FieldRead)
    assert frontend._context.flow.lambda_counter == 1
