"""The first independent frontend components keep import/Port contracts intact."""

from __future__ import annotations

import ast

import pytest
from demo_ports_pyinto import interface_mapping_registry

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import Literal
from pyinto.frontend.context import NameState, ParseContext
from pyinto.frontend.decorators import DecoratorRule, default_decorators
from pyinto.frontend.imports import ImportNormalizer
from pyinto.frontend.interface_mapping import InterfaceMappingNormalizer


def _import(source: str) -> ast.ImportFrom:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.ImportFrom)
    return node


def test_import_component_resolves_registered_port_and_decorator_together() -> None:
    names = NameState()
    decorators = default_decorators()
    decorators.register(DecoratorRule("extensions.marker", "method", "static-alias"))
    import_normalizer = ImportNormalizer(
        names, interface_mapping_registry(), decorators
    )
    import_normalizer.accept(_import("from extensions import marker as m"))
    import_normalizer.accept(_import("from demo_ports.device import is_ready as ready"))
    assert decorators.imported_names == {"m"}
    assert names.interface_aliases == {"ready": "demo_ports.device.is_ready"}
    with pytest.raises(UnsupportedPython, match="Duplicate or reserved import alias"):
        import_normalizer.accept(_import("from demo_ports.device import is_ready as m"))


def test_independent_port_component_uses_only_supplied_services() -> None:
    ctx = ParseContext()
    registry = interface_mapping_registry()
    ImportNormalizer(ctx.names, registry, default_decorators()).accept(
        _import("from demo_ports.device import is_ready as ready")
    )
    component = InterfaceMappingNormalizer(
        ctx, registry, value=lambda _: Literal(1), declaration_scope=lambda: ()
    )
    call_stmt = ast.parse("ready()").body[0]
    assert isinstance(call_stmt, ast.Expr) and isinstance(call_stmt.value, ast.Call)
    value = component.mapped_call(call_stmt.value)
    assert value is not None
    call_stmt = ast.parse("unknown()").body[0]
    assert isinstance(call_stmt, ast.Expr) and isinstance(call_stmt.value, ast.Call)
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        component.mapped_call(call_stmt.value)


def test_failure_isolation_with_imports_and_normalizer_across_parses() -> None:
    frontend = PythonFrontend(interface_mapping_registry())
    program = frontend.parse(
        "from demo_ports.device import is_ready as ready\n"
        'if ready():\n    print("ok")\n'
    )
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        frontend.parse("if ready():\n    print('bad')\n")
    assert (
        frontend.parse(
            "from demo_ports.device import is_ready as ready\n"
            'if ready():\n    print("ok")\n'
        )
        == program
    )
