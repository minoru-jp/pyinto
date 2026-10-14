"""Module organization must not weaken Model and Frontend contract boundaries."""

from __future__ import annotations

import ast

import pytest

from pyinto.constructs import (
    ClassDefinition,
    Construct,
    FunctionDefinition,
    ListValue,
    Value,
)
from pyinto.constructs.classes import ClassDefinition as DefinedClass
from pyinto.constructs.collections import ListValue as DefinedList
from pyinto.constructs.functions import FunctionDefinition as DefinedFunction
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.frontend.decorators import (
    DecoratorRule,
    default_decorators,
)
from tests.model_sources import construct_trees


def test_construct_modules_have_one_identity_per_definition() -> None:
    assert DefinedList is ListValue
    assert DefinedFunction is FunctionDefinition
    assert DefinedClass is ClassDefinition
    assert issubclass(ListValue, Value)
    assert issubclass(ClassDefinition, Construct)


def test_construct_model_submodules_do_not_import_frontend_or_realization() -> None:
    forbidden = ("pyinto.frontend", "pyinto.realizations", "pyinto.targets")
    for tree in construct_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any((node.module or "").startswith(x) for x in forbidden)
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(x) for x in forbidden for alias in node.names
                )


def test_frt_058_decorator_registry_is_explicit_and_parse_scoped() -> None:
    registry = default_decorators()
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register(DecoratorRule("dataclasses.dataclass", "class", "other"))
    assert registry.lookup("staticmethod", target="method", shadowed=set()) is not None
    assert registry.lookup("staticmethod", target="class", shadowed=set()) is None
    assert (
        registry.lookup("staticmethod", target="method", shadowed={"staticmethod"})
        is None
    )
    assert registry.lookup("dataclass", target="class", shadowed=set()) is None
    assert registry.bind_import("dataclasses.dataclass", "dc")
    assert registry.lookup("dc", target="class", shadowed=set()) is not None
    fresh = registry.fresh()
    assert fresh.lookup("dc", target="class", shadowed=set()) is None
    assert fresh.lookup("classmethod", target="method", shadowed=set()) is not None


def test_frt_058_unimplemented_registered_effects_are_rejected() -> None:
    decorators = default_decorators()
    decorators.register(DecoratorRule("demo.annotate", "class", "interface-contract"))
    decorators.register(DecoratorRule("demo.mark", "method", "custom-method"))
    frontend = PythonFrontend(decorators=decorators)
    with pytest.raises(UnsupportedPython, match="No normalizer for registered class"):
        frontend.parse("from demo import annotate\n@annotate\nclass A:\n    pass\n")
    with pytest.raises(UnsupportedPython, match="No normalizer for registered method"):
        frontend.parse(
            "from demo import mark\nclass A:\n"
            "    @mark\n    def f(self) -> int:\n        return 1\n"
        )
    with pytest.raises(UnsupportedPython, match="decorator"):
        frontend.parse("@annotate\nclass B:\n    pass\n")


def test_frt_058_library_can_export_registered_decorators_alongside_ports() -> None:
    from pyinto.constructs import BooleanLiteral
    from pyinto.interface_mapping import (
        InterfaceFunctionMapping,
        InterfaceMappingRegistry,
    )

    decorators = default_decorators()
    decorators.register(DecoratorRule("demo.annotate", "class", "interface-contract"))
    interface_mappings = InterfaceMappingRegistry(
        (InterfaceFunctionMapping("demo.is_ok", (), lambda _: BooleanLiteral(True)),)
    )
    program = PythonFrontend(interface_mappings, decorators=decorators).parse(
        "from demo import annotate, is_ok\nif is_ok():\n    print('ok')\n"
    )
    assert program.body.children
