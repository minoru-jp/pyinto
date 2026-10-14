"""Class normalization is composed per parse, with narrow service dependencies."""

from __future__ import annotations

import ast

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import InstanceType, MethodDispatch
from pyinto.frontend.classes import ClassNormalizer, ClassServices
from pyinto.frontend.context import ParseContext
from pyinto.frontend.decorators import default_decorators


def test_class_normalizer_collects_types_without_parser_inheritance() -> None:
    context = ParseContext()
    normalizer = ClassNormalizer(
        context,
        default_decorators(),
        object(),  # type: ignore[arg-type] - collection needs no services
    )
    nodes = ast.parse("class Base:\n    pass\nclass Child(Base):\n    pass").body
    normalizer._collect_classes(nodes)
    assert (
        context.classes.class_types["Child"].base is context.classes.class_types["Base"]
    )
    assert context.classes.class_types["Child"] == InstanceType(
        "Child", base=InstanceType("Base")
    )
    assert not issubclass(PythonFrontend, ClassNormalizer)


def test_class_service_contract_exposes_only_cross_domain_operations() -> None:
    assert {
        name
        for name, member in vars(ClassServices).items()
        if name.startswith("_") and not name.startswith("__") and callable(member)
    } == {
        "_annotation",
        "_collect_functions",
        "_function_definition",
        "_declared_call_arguments",
        "_lookup_symbol",
        "_lookup_function",
        "_value",
        "_function_value_call",
        "_is_super_expression",
    }
    assert "_class_definition" not in vars(ClassServices)
    assert "_class_decoration" not in vars(ClassServices)


def test_class_normalizer_per_parse_uses_shared_services() -> None:
    frontend = PythonFrontend()
    old = frontend._classes
    source = (
        "class Base:\n"
        "    def __init__(self) -> None:\n"
        "        self.x: int = 1\n"
        "    def get(self) -> int:\n"
        "        return self.x\n"
        "class Child(Base):\n"
        "    def __init__(self) -> None:\n"
        "        super().__init__()\n"
        "    def get(self) -> int:\n"
        "        return super().get()\n"
        "obj: Child = Child()\n"
        "result: int = obj.get()\n"
    )
    model = frontend.parse(source)
    assert frontend._classes is not old
    assert frontend._classes._context is frontend._context
    assert frontend._classes._decorators is frontend._decorators
    assert frontend._classes._services is frontend
    assert frontend._classes._context is frontend._functions._context
    assert frontend._classes._context is frontend._statements._context
    assert frontend._classes._context is frontend._expressions._context
    assert frontend.parse(source) == model
    assert frontend._classes._context is frontend._context
    assert frontend._classes is not old
    # The class component preserves the super dispatch in the Model.
    child = model.body.children[1]
    assert child.methods[1].body.children[0].value.dispatch is MethodDispatch.SUPER


def test_class_decorator_still_applies_once_per_parse() -> None:
    source = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Point:\n"
        "    x: int\n"
        "    y: int = 3\n"
        "point: Point = Point(1)\n"
    )
    frontend = PythonFrontend()
    assert frontend.parse(source) == PythonFrontend().parse(source)
    assert len(frontend._context.classes.class_decorations) == 1
    assert frontend.parse(source) == PythonFrontend().parse(source)
    assert len(frontend._context.classes.class_decorations) == 1


def test_invalid_class_does_not_leak_into_next_parse() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython):
        frontend.parse("class Broken:\n    pass\n")
    assert frontend._context.classes.active_class_type is None
    assert frontend._context.classes.class_module_functions == {}
    valid = (
        "class Fixed:\n"
        "    def __init__(self) -> None:\n"
        "        self.x: int = 1\n"
        "result: Fixed = Fixed()\n"
    )
    assert frontend.parse(valid) == PythonFrontend().parse(valid)
    assert "Broken" not in frontend._context.classes.class_types
