"""FRT_058: explicit name resolution and opt-in, non-evaluating effect adapters."""

from __future__ import annotations

import ast

import pytest

from pyinto.constructs import (
    Block,
    ClassDefinition,
    FunctionDefinition,
    Literal,
    MethodKind,
    Return,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython
from pyinto.frontend.decorator_effects import dataclass_plan
from pyinto.frontend.decorators import (
    ClassDecorationPlan,
    DecoratorRegistry,
    DecoratorRule,
    default_decorators,
)


def test_custom_method_effect_uses_registered_adapter_not_builtin_name() -> None:
    rules = default_decorators()
    rules.register(DecoratorRule("external.marker", "method", "static-alias"))
    rules.register_method_normalizer("static-alias", lambda _: MethodKind.STATIC)
    program = PythonFrontend(decorators=rules).parse(
        "from external import marker as m\n"
        "class C:\n"
        "    def __init__(self) -> None:\n        return\n"
        "    @m\n"
        "    def f(v: int) -> int:\n        return v\n"
        "result: int = C.f(4)\n"
    )
    cls = program.body.children[0]
    assert isinstance(cls, ClassDefinition)
    assert cls.signature.method("f").method_kind is MethodKind.STATIC


def test_custom_class_effect_can_supply_explicit_synthetic_model_structure() -> None:
    rules = default_decorators()
    rules.register(DecoratorRule("external.record", "class", "record"))
    seen: list[str] = []

    def normalize(node: ast.ClassDef) -> ClassDecorationPlan:
        seen.append(node.name)
        return dataclass_plan(node)

    rules.register_class_normalizer("record", normalize)
    frontend = PythonFrontend(decorators=rules)
    source = "from external import record as r\n@r\nclass C:\n    x: int\np: C = C(7)\n"
    for _ in range(2):
        program = frontend.parse(source)
        cls = program.body.children[0]
        assert isinstance(cls, ClassDefinition)
        assert [field.name for field in cls.signature.fields] == ["x"]
    # Declaration collection and class construction share a single plan.
    assert seen == ["C", "C"]


def test_custom_function_effect_rewrites_model_not_source_execution() -> None:
    rules = default_decorators()
    rules.register(DecoratorRule("external.constant", "function", "constant-nine"))
    rules.register_function_normalizer(
        "constant-nine",
        lambda _node, model: FunctionDefinition(
            model.signature, Block((Return(Literal(9)),))
        ),
    )
    program = PythonFrontend(decorators=rules).parse(
        "from external import constant as c\n"
        "@c\ndef value() -> int:\n    return 1\n"
        "out: int = value()\n"
    )
    fn = program.body.children[0]
    assert isinstance(fn, FunctionDefinition)
    result = fn.body.children[0]
    assert isinstance(result, Return)
    assert result.value == Literal(9)


def test_registered_name_without_normalizer_is_rejected_in_all_declaration_sites() -> (
    None
):
    rules = default_decorators()
    rules.register(DecoratorRule("external.function", "function", "unknown"))
    rules.register(DecoratorRule("external.method", "method", "unknown"))
    rules.register(DecoratorRule("external.class_marker", "class", "unknown"))
    frontend = PythonFrontend(decorators=rules)
    with pytest.raises(UnsupportedPython, match="No normalizer.*function decorator"):
        frontend.parse(
            "from external import function\n@function\ndef x() -> int:\n    return 1\n"
        )
    with pytest.raises(UnsupportedPython, match="No normalizer.*method decorator"):
        frontend.parse(
            "from external import method\n"
            "class C:\n    def __init__(self) -> None:\n        pass\n"
            "    @method\n    def x(self) -> int:\n        return 1\n"
        )
    with pytest.raises(UnsupportedPython, match="No normalizer.*class decorator"):
        frontend.parse(
            "from external import class_marker\n@class_marker\nclass C:\n    pass\n"
        )


def test_adapter_must_preserve_function_signature() -> None:
    rules = default_decorators()
    rules.register(DecoratorRule("external.mark", "function", "bad"))
    rules.register_function_normalizer("bad", lambda _node, _model: Literal(1))  # type: ignore[arg-type,return-value]
    with pytest.raises(UnsupportedPython, match="must preserve the declared"):
        PythonFrontend(decorators=rules).parse(
            "from external import mark\n@mark\ndef x() -> int:\n    return 1\n"
        )


def test_normalizers_are_explicit_and_registration_is_independent_per_frontend() -> (
    None
):
    registry = DecoratorRegistry((DecoratorRule("demo.mark", "method", "tag"),))
    with pytest.raises(ValueError, match="Unregistered"):
        registry.register_class_normalizer("tag", lambda _: ClassDecorationPlan())
    registry.register_method_normalizer("tag", lambda _: MethodKind.STATIC)
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register_method_normalizer("tag", lambda _: MethodKind.CLASS)
    assert registry.bind_import("demo.mark", "m")
    fresh = registry.fresh()
    assert fresh.lookup("m", target="method", shadowed=set()) is None
    assert fresh.bind_import("demo.mark", "again")
    rule = fresh.lookup("again", target="method", shadowed=set())
    assert rule is not None
    assert (
        fresh.method_kind(rule, ast.parse("def f(): pass").body[0]) is MethodKind.STATIC
    )  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "source",
    [
        (
            "class C:\n    def __init__(self) -> None:\n        pass\n"
            "    @staticmethod()\n    def m() -> None:\n        return\n"
        ),
        (
            "class C:\n    def __init__(self) -> None:\n        pass\n"
            "    @staticmethod\n    @classmethod\n    def m() -> None:\n        return\n"
        ),
        "from dataclasses import dataclass\n@dataclass()\nclass C:\n    x: int\n",
    ],
)
def test_python_decorator_evaluation_and_stacking_still_rejected(source: str) -> None:
    with pytest.raises(UnsupportedPython):
        PythonFrontend().parse(source)
