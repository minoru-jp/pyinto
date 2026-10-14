"""Phase 25: static keyword call bindings preserve source expression order."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    ConstructError,
    FunctionCall,
    InstanceCreation,
    Literal,
    MethodCall,
    MethodDispatch,
    ValueKind,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def statements(source: str):
    return PythonFrontend().parse(source).body.children


FUNCTION = """\ndef f(x: int, y: int, z: int) -> int:
    return x + y + z
"""

CLASS = """\nclass Base:
    def __init__(self, x: int, y: int) -> None:
        self.x: int = x
        self.y: int = y

    def total(self, x: int, y: int) -> int:
        return self.x + x + y

class Derived(Base):
    def __init__(self, x: int, y: int) -> None:
        super().__init__(y=y, x=x)

    def total(self, x: int, y: int) -> int:
        return super().total(y=y, x=x)
"""


def test_all_keywords_bind_by_name_without_new_construct() -> None:
    body = statements(FUNCTION + "result: int = f(z=30, x=10, y=20)")
    call = body[-1].value
    assert isinstance(call, FunctionCall)
    assert tuple(v.value for v in call.arguments) == (10, 20, 30)
    assert call.argument_evaluation_order == (2, 0, 1)
    assert tuple(v.value for v in call.evaluation_arguments) == (30, 10, 20)
    assert call.parts()["arg0"] == Literal(10)
    assert call.parts()["arg2"] == Literal(30)


def test_mixed_calls_and_legacy_positional_behavior() -> None:
    body = statements(FUNCTION + "a: int = f(1, z=3, y=2)\nb: int = f(1, 2, 3)")
    first, second = body[-2].value, body[-1].value
    assert isinstance(first, FunctionCall)
    assert first.argument_evaluation_order == (0, 2, 1)
    assert isinstance(second, FunctionCall)
    assert second.argument_evaluation_order == (0, 1, 2)
    assert tuple(v.value for v in second.arguments) == (1, 2, 3)


def test_nested_direct_calls_retain_explicit_source_order() -> None:
    body = statements(FUNCTION + "result: int = f(z=f(x=3, y=4, z=5), x=1, y=2)")
    outer = body[-1].value
    assert isinstance(outer, FunctionCall)
    assert outer.argument_evaluation_order == (2, 0, 1)
    inner = outer.arguments[2]
    assert isinstance(inner, FunctionCall)
    assert inner.argument_evaluation_order == (0, 1, 2)


def test_forward_reference_and_nested_function_call() -> None:
    source = """\ndef outer() -> int:
    def nested(x: int, y: int) -> int:
        return x + y
    return nested(y=7, x=8)
result: int = outer()
"""
    body = statements(source)
    nested_call = body[0].body.children[-1].value
    assert isinstance(nested_call, FunctionCall)
    assert nested_call.signature.scope == ("outer",)
    assert nested_call.argument_evaluation_order == (1, 0)


def test_class_initializer_keyword_arguments() -> None:
    body = statements(CLASS + "obj: Derived = Derived(y=2, x=1)")
    create = body[-1].value
    assert isinstance(create, InstanceCreation)
    assert create.argument_evaluation_order == (1, 0)
    assert tuple(v.value for v in create.arguments) == (1, 2)


def test_method_and_super_calls_with_keywords() -> None:
    body = statements(
        CLASS + "obj: Base = Derived(2, 4)\nresult: int = obj.total(y=20, x=10)"
    )
    call = body[-1].value
    assert isinstance(call, MethodCall)
    assert call.dispatch is MethodDispatch.VIRTUAL
    assert call.argument_evaluation_order == (1, 0)
    derived = body[1]
    init_call = derived.methods[0].body.children[0].value
    super_call = derived.methods[1].body.children[0].value
    assert isinstance(init_call, MethodCall)
    assert init_call.dispatch is MethodDispatch.SUPER
    assert init_call.argument_evaluation_order == (1, 0)
    assert isinstance(super_call, MethodCall)
    assert super_call.dispatch is MethodDispatch.SUPER
    assert super_call.argument_evaluation_order == (1, 0)


def test_method_call_without_keyword_uses_default_evaluation_order() -> None:
    body = statements(CLASS + "obj: Base = Base(1, 2)\nx: int = obj.total(3, 4)")
    call = body[-1].value
    assert isinstance(call, MethodCall)
    assert call.evaluation_order == ()
    assert call.argument_evaluation_order == (0, 1)


@pytest.mark.parametrize(
    ("suffix", "message"),
    [
        ("f(x=1, y=2)", "Missing required"),
        ("f(q=1, y=2, z=3)", "Unknown keyword"),
        ("f(1, x=2, z=3)", "Duplicate argument"),
        ("f(x=1, x=2, y=3, z=4)", "Duplicate argument"),
        ("f(**{'x': 1, 'y': 2, 'z': 3})", "Expanded keyword"),
        ("f(*(1, 2, 3))", "Expanded call"),
        ("f(x='bad', y=2, z=3)", "argument type mismatch"),
    ],
)
def test_invalid_function_keyword_bindings(suffix: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        statements(FUNCTION + f"result: int = {suffix}")


@pytest.mark.parametrize(
    ("expr", "message"),
    [
        ("Derived(x=1)", "Missing required"),
        ("Derived(x=1, y=2, z=3)", "Unknown keyword"),
        ("Derived(1, x=2)", "Duplicate argument"),
        ("Derived(x='bad', y=2)", "initializer argument mismatch"),
    ],
)
def test_invalid_constructor_keywords(expr: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        statements(CLASS + f"obj: Derived = {expr}")


@pytest.mark.parametrize(
    ("expr", "message"),
    [
        ("obj.total(z=1, y=2)", "Unknown keyword"),
        ("obj.total(x=1)", "Missing required"),
        ("obj.total(x='bad', y=2)", "Method argument mismatch"),
    ],
)
def test_invalid_method_keywords(expr: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        statements(CLASS + f"obj: Base = Base(1, 2)\nx: int = {expr}")


def test_function_values_still_reject_keywords() -> None:
    source = """\nfrom typing import Callable

def identity(n: int) -> int:
    return n

f: Callable[[int], int] = identity
x: int = f(n=3)
"""
    with pytest.raises(UnsupportedPython, match="positional arguments only"):
        statements(source)


def test_ordinary_signature_is_unchanged() -> None:
    body = statements(FUNCTION + "result: int = f(x=1, y=2, z=3)")
    signature = body[0].signature
    assert signature.parameters[0].kind is ValueKind.INTEGER
    assert isinstance(body[-1].value, FunctionCall)


def test_model_enforces_complete_source_order_permutation() -> None:
    call = statements(FUNCTION + "result: int = f(1, 2, 3)")[-1].value
    assert isinstance(call, FunctionCall)
    for order in ((1, 1, 0), (0, 1), (-1, 0, 2), (True, 1, 2)):
        with pytest.raises(ConstructError, match="evaluation order"):
            FunctionCall(call.signature, call.arguments, order)


def test_no_target_realization_is_invented() -> None:
    import pyinto
    from tests.support.c_realizer import c_bindings

    program = PythonFrontend().parse(FUNCTION + "result: int = f(z=3, y=2, x=1)")
    with pytest.raises(
        ConstructError, match="No .* realization for FunctionDefinition"
    ):
        pyinto.realize(program, realizations=c_bindings())
