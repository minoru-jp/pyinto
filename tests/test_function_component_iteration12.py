"""Function normalization is a composed, per-parse service, not a mixin."""

from __future__ import annotations

import ast

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import Literal, Symbol, ValueKind, ValueType
from pyinto.frontend.context import ParseContext
from pyinto.frontend.decorators import default_decorators
from pyinto.frontend.functions import FunctionNormalizer, FunctionServices


class _OnlyValues:
    """Enough cross-domain behavior to normalize explicit call arguments."""

    def _value(self, node: ast.expr, expected: ValueType | None = None) -> Literal:
        assert isinstance(node, ast.Constant) and type(node.value) is int
        assert expected is not None and expected.kind is ValueKind.INTEGER
        return Literal(node.value)


def test_function_domain_operates_without_frontend_inheritance() -> None:
    assert not issubclass(PythonFrontend, FunctionNormalizer)
    ctx = ParseContext()
    normalizer = FunctionNormalizer(
        ctx,
        default_decorators(),
        _OnlyValues(),  # type: ignore[arg-type]
    )
    params = (
        Symbol("x", ValueType(ValueKind.INTEGER), "int"),
        Symbol("y", ValueType(ValueKind.INTEGER), "int"),
    )
    node = ast.parse("f(y=1, x=2)", mode="eval").body
    assert isinstance(node, ast.Call)
    values, evaluation_order, omitted = normalizer._declared_call_arguments(
        node, params
    )
    assert values == (Literal(2), Literal(1))
    assert evaluation_order == (1, 0)
    assert omitted == ()
    assert ctx.names.symbols == {}


def test_function_service_surface_is_only_cross_domain_operations() -> None:
    assert set(FunctionServices.__dict__) & {
        "_annotation",
        "_method_kind",
        "_block",
        "_value",
    } == {"_annotation", "_method_kind", "_block", "_value"}
    assert "_collect_functions" not in vars(FunctionServices)
    assert "_lookup_symbol" not in vars(FunctionServices)
    assert "_lambda_value" not in vars(FunctionServices)


def test_function_normalizer_is_fresh_and_shares_one_parse_context() -> None:
    frontend = PythonFrontend()
    first = frontend._functions
    program = "def add(x: int, y: int) -> int:\n    return x + y\nz: int = add(1, 2)"
    result = frontend.parse(program)
    assert frontend._functions is not first
    assert frontend._functions._context is frontend._context
    assert frontend._functions._services is frontend
    assert frontend._functions._decorators is frontend._decorators
    assert frontend._expressions._context is frontend._functions._context
    assert frontend._statements._context is frontend._functions._context
    new = frontend._functions
    assert frontend.parse(program) == result
    assert frontend._functions is not new


def test_function_component_preserves_nested_captures_and_lambda() -> None:
    source = (
        "from typing import Callable\n"
        "def make(x: int) -> Callable[[int], int]:\n"
        "    def internal(y: int) -> int:\n"
        "        return x + y\n"
        "    fn: Callable[[int], int] = lambda y: internal(y)\n"
        "    return fn\n"
        "result: Callable[[int], int] = make(2)\n"
    )
    frontend = PythonFrontend()
    assert frontend.parse(source) == PythonFrontend().parse(source)
    assert frontend._context.flow.lambda_counter == 1


def test_failed_function_parse_does_not_leak_scope_or_functions() -> None:
    frontend = PythonFrontend()
    bad = "def make(x: int) -> int:\n    return missing\n"
    with pytest.raises(UnsupportedPython):
        frontend.parse(bad)
    assert frontend._context.names.active_function is None
    assert frontend._context.names.enclosing_scopes == []
    assert frontend.parse("def make(x: int) -> int:\n    return x\n") == (
        PythonFrontend().parse("def make(x: int) -> int:\n    return x\n")
    )
