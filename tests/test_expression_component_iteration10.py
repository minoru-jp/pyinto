"""Expression normalizer is independent, yet shares the parse's exact state."""

from __future__ import annotations

import ast

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import Arithmetic, Literal
from pyinto.frontend.context import ParseContext
from pyinto.frontend.expressions import ExpressionNormalizer
from pyinto.frontend.interface_mapping import InterfaceMappingNormalizer
from pyinto.interface_mapping import InterfaceMappingRegistry


class _NoDomainCalls:
    """Any operation on a domain not needed by a scalar expression is a bug."""

    def __getattr__(self, name: str) -> None:
        raise AssertionError(f"Unexpected cross-domain call: {name}")


def test_expressions_can_normalize_without_inheriting_frontend() -> None:
    context = ParseContext()
    expressions = ExpressionNormalizer(
        context,
        InterfaceMappingNormalizer(
            context,
            InterfaceMappingRegistry(),
            value=lambda _: Literal(1),
            declaration_scope=lambda: (),
        ),
        _NoDomainCalls(),  # type: ignore[arg-type] - intentionally minimal test double
    )
    tree = ast.parse("(1 + 2) * 3", mode="eval")
    result = expressions._value(tree.body)
    assert isinstance(result, Arithmetic)
    assert result.value_type.kind == Literal(1).value_type.kind


def test_expression_services_are_fresh_per_parse() -> None:
    frontend = PythonFrontend()
    initial_context = frontend._context
    initial_expressions = frontend._expressions
    source = "x: int = 1\ny: int = x + 2"
    expected = frontend.parse(source)
    assert frontend._context is not initial_context
    assert frontend._expressions is not initial_expressions
    assert frontend._expressions._context is frontend._context
    assert (
        frontend._expressions._interface_mapping_normalizer
        is frontend._interface_mapping_normalizer
    )
    assert frontend._expressions._services is frontend
    previous = frontend._expressions
    assert frontend.parse(source) == expected
    assert frontend._expressions is not previous
    assert frontend._expressions._context is frontend._context


def test_expressions_and_callables_use_the_same_context() -> None:
    frontend = PythonFrontend()
    source = (
        "from typing import Callable\n"
        "def apply(f: Callable[[int], int], x: int) -> int:\n"
        "    return f(x)\n"
        "base: int = 3\n"
        "func: Callable[[int], int] = lambda x: x + base\n"
        "result: int = apply(func, base)\n"
    )
    result = frontend.parse(source)
    assert frontend._context.flow.lambda_counter == 1
    assert frontend.parse(source) == result
    assert frontend._context.flow.lambda_counter == 1


def test_failed_expression_parse_does_not_keep_component_or_names() -> None:
    frontend = PythonFrontend()
    baseline = frontend.parse("x: int = 3")
    stale_expressions = frontend._expressions
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        frontend.parse("other: int = x + unknown")
    assert frontend._expressions is not stale_expressions
    assert frontend.parse("x: int = 3") == baseline
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        frontend.parse("result: int = other")
