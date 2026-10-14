"""Regression checks for the phase-30 frontend architecture change."""

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.frontend.classes import ClassNormalizer
from pyinto.frontend.context import ParseContext
from pyinto.frontend.expressions import ExpressionNormalizer
from pyinto.frontend.functions import FunctionNormalizer
from pyinto.frontend.interface_mapping import InterfaceMappingNormalizer
from pyinto.frontend.statements import StatementNormalizer


def test_implementation_domains_are_explicit_and_complete() -> None:
    assert not issubclass(PythonFrontend, StatementNormalizer)
    assert PythonFrontend._statement is not StatementNormalizer._statement
    assert not issubclass(PythonFrontend, ExpressionNormalizer)
    assert PythonFrontend._value is not ExpressionNormalizer._value
    assert not issubclass(PythonFrontend, FunctionNormalizer)
    assert (
        PythonFrontend._function_definition
        is not FunctionNormalizer._function_definition
    )
    assert not issubclass(PythonFrontend, ClassNormalizer)
    assert PythonFrontend._class_definition is not ClassNormalizer._class_definition
    assert not issubclass(PythonFrontend, InterfaceMappingNormalizer)
    assert not hasattr(PythonFrontend, "_mapped_call")
    assert not hasattr(PythonFrontend, "_object_constructor")
    # Cross-domain connections use narrow service contracts rather than
    # a shared, unimplemented superclass of placeholder methods.
    assert not hasattr(PythonFrontend, "_class_fields")
    assert not hasattr(PythonFrontend, "_class_decoration")


def test_parse_context_has_no_shared_mutable_state() -> None:
    first, second = ParseContext(), ParseContext()
    first.names.type_aliases.add("missing")
    first.classes.initialized_fields.add("missing")
    first.flow.lambda_counter = 10
    assert not second.names.type_aliases
    assert not second.classes.initialized_fields
    assert second.flow.lambda_counter == 0


def test_frontend_reuse_does_not_leak_symbols_after_failure() -> None:
    frontend = PythonFrontend()
    original = frontend.parse("x: int = 1")
    with pytest.raises(UnsupportedPython):
        frontend.parse("y: int = 2\nz: int = missing")
    assert frontend.parse("x: int = 1") == original
    with pytest.raises(UnsupportedPython):
        frontend.parse("z: int = y")


def test_frontend_reuse_does_not_leak_decorator_aliases() -> None:
    frontend = PythonFrontend()
    source = (
        "from dataclasses import dataclass as dc\n@dc\nclass Record:\n    value: int\n"
    )
    result = frontend.parse(source)
    assert frontend.parse(source) == result
    with pytest.raises(UnsupportedPython):
        frontend.parse("@dc\nclass Record:\n    value: int\n")
