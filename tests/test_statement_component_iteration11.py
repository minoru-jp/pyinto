"""The statement domain is independently composed with the other normalizers."""

from __future__ import annotations

import ast

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import Call, Literal
from pyinto.frontend.context import ParseContext
from pyinto.frontend.interface_mapping import InterfaceMappingNormalizer
from pyinto.frontend.statement_services import StatementServices
from pyinto.frontend.statements import StatementNormalizer
from pyinto.interface_mapping import InterfaceMappingRegistry


class _OnlyValues:
    """No class, function, or scope service is needed for a simple print."""

    def _value(self, node: ast.expr, expected: object = None) -> Literal:
        assert isinstance(node, ast.Constant)
        assert type(node.value) is str
        return Literal(node.value)


def test_statements_normalize_with_no_frontend_inheritance() -> None:
    ctx = ParseContext()
    mapping = InterfaceMappingNormalizer(
        ctx,
        InterfaceMappingRegistry(),
        value=lambda _: Literal("unused"),
        declaration_scope=lambda: (),
    )
    statements = StatementNormalizer(
        ctx,
        mapping,
        _OnlyValues(),  # type: ignore[arg-type] - intentionally narrow test double
    )
    result = statements._block(ast.parse('print("ok")').body)
    assert len(result.children) == 1
    assert isinstance(result.children[0], Call)
    assert ctx.flow.block_depth == 0


def test_statement_services_and_state_are_per_parse() -> None:
    frontend = PythonFrontend()
    original_statements = frontend._statements
    expected = frontend.parse("x: int = 1\nif x > 0:\n    print('yes')")
    assert frontend._statements is not original_statements
    assert frontend._statements._context is frontend._context
    assert (
        frontend._statements._interface_mapping_normalizer
        is frontend._interface_mapping_normalizer
    )
    assert frontend._statements._services is frontend
    assert (
        frontend._statements._interface_mapping_normalizer
        is frontend._expressions._interface_mapping_normalizer
    )
    old = frontend._statements
    assert frontend.parse("x: int = 1\nif x > 0:\n    print('yes')") == expected
    assert frontend._statements is not old


def test_statement_component_crosses_function_and_exception_boundaries() -> None:
    frontend = PythonFrontend()
    source = (
        "def work(x: int) -> int:\n"
        "    try:\n"
        "        if x > 0:\n"
        "            return x\n"
        "        raise ValueError('negative')\n"
        "    except ValueError:\n"
        "        return 0\n"
        "result: int = work(1)\n"
    )
    baseline = frontend.parse(source)
    assert frontend.parse(source) == baseline
    assert frontend._context.flow.block_depth == 0


def test_failed_nested_statement_does_not_leak_depth_or_symbols() -> None:
    frontend = PythonFrontend()
    source = "x: int = 1\nwhile x > 0:\n    missing = x\n"
    with pytest.raises(UnsupportedPython, match="explicit type annotation"):
        frontend.parse(source)
    assert frontend._context.flow.block_depth == 0
    assert frontend._context.flow.loop_depth == 0
    assert frontend.parse("x: int = 1") == PythonFrontend().parse("x: int = 1")


def test_statement_service_surface_does_not_expose_whole_frontend() -> None:
    # The statements component does not need to drive its own recursive dispatch
    # via its parent, and does not require direct access to the entire parser.
    assert not issubclass(PythonFrontend, StatementNormalizer)
    assert "_statement" not in vars(StatementServices)
    assert "_block" not in vars(StatementServices)
