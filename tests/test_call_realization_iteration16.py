"""Iteration 16: combined call obligations and actual Slot composition."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    ClassDefinition,
    ClassMethodCall,
    ClassReceiverCreation,
    Construct,
    ConstructError,
    FunctionCall,
    InstanceCreation,
    Literal,
    MethodCall,
    MethodDispatch,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
)

_COMPOUND_SOURCE = """
class Base:
    def __init__(self, x: int, y: int = 2, z: int = 3) -> None:
        self.x: int = x
        self.y: int = y
        self.z: int = z
    def total(self, x: int, y: int = 2, z: int = 3) -> int:
        return x + y + z
    @classmethod
    def create(cls, x: int, y: int = 2, z: int = 3) -> Base:
        return cls(z=z, x=x)
class Derived(Base):
    def __init__(self, x: int, y: int = 2, z: int = 3) -> None:
        super().__init__(z=z, x=x)
    def total(self, x: int, y: int = 2, z: int = 3) -> int:
        return super().total(z=z, x=x)
obj: Base = Derived(z=8, x=4)
v: int = obj.total(z=9, x=5)
created: Base = Derived.create(z=11, x=6)
"""


def _calls() -> dict[str, Construct]:
    parsed = PythonFrontend().parse(_COMPOUND_SOURCE)
    base, derived = parsed.body.children[:2]
    assert isinstance(base, ClassDefinition)
    assert isinstance(derived, ClassDefinition)
    base_methods = {m.signature.name: m for m in base.methods}
    derived_methods = {m.signature.name: m for m in derived.methods}
    results: dict[str, Construct] = {
        "factory": base_methods["create"].body.children[0].value,
        "super": derived_methods["total"].body.children[0].value,
        "new": parsed.body.children[2].value,
        "virtual": parsed.body.children[3].value,
        "class": parsed.body.children[4].value,
    }
    assert isinstance(results["factory"], ClassReceiverCreation)
    assert isinstance(results["super"], MethodCall)
    assert isinstance(results["new"], InstanceCreation)
    assert isinstance(results["virtual"], MethodCall)
    assert isinstance(results["class"], ClassMethodCall)
    return results


def test_five_call_forms_require_combined_per_instance_contracts() -> None:
    calls = _calls()
    for call in calls.values():
        assert call.argument_evaluation_order == (2, 0, 1)
        assert call.omitted_arguments == (1,)
        assert {
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
        } <= required_contracts(call)

    assert {"method.dispatch.super", "method.lookup.lexical_base"} <= (
        required_contracts(calls["super"])
    )
    assert "method.dispatch.virtual" in required_contracts(calls["virtual"])
    for name in ("factory", "class"):
        assert "class_receiver.runtime_identity" in required_contracts(calls[name])


def test_each_missing_contract_fails_before_selector_or_requirements() -> None:
    for node in _calls().values():
        for missing in required_contracts(node):
            called: list[Construct] = []

            def selector(
                model: Construct, _: EmitContext, seen: list[Construct] = called
            ) -> str:
                seen.append(model)
                return "${arg2}, ${arg0}"

            @realizes(type(node))
            class Entry:
                supports = tuple(sorted(required_contracts(node) - {missing}))
                render = selector
                requires = ("unsafe.h",)

            registry = RealizationRegistry("check", (Entry,))
            context = EmitContext(registry)
            with pytest.raises(
                ConstructError, match="does not support contracts"
            ) as error:
                registry.recipe(node, context)
            assert missing in str(error.value)
            assert not called
            assert not context.headers


def test_super_and_virtual_need_distinct_declared_capabilities() -> None:
    calls = _calls()
    assert isinstance(calls["virtual"], MethodCall)
    assert isinstance(calls["super"], MethodCall)
    assert calls["virtual"].dispatch is MethodDispatch.VIRTUAL
    assert calls["super"].dispatch is MethodDispatch.SUPER

    @realizes(MethodCall)
    class Virtual:
        supports = tuple(sorted(required_contracts(calls["virtual"])))
        template = "${receiver}.${method}(z=${arg2}, x=${arg0})"

    registry = RealizationRegistry("check", (Virtual,))
    assert registry.recipe(calls["virtual"], EmitContext(registry))
    with pytest.raises(ConstructError, match="method.dispatch.super"):
        Composer(registry).layout(calls["super"])


def test_direct_templates_cannot_claim_support_and_drop_or_reorder_arguments() -> None:
    source = """
def f(x: int, y: int = 7, z: int = 9) -> int:
    return x + y + z
result: int = f(z=4, x=1)
"""
    node = PythonFrontend().parse(source).body.children[-1].value
    assert isinstance(node, FunctionCall)
    claimed = tuple(sorted(required_contracts(node)))

    for source_template, problem in (
        ("f(${arg0},${arg1},${arg2})", "source argument evaluation order"),
        ("f(x=${arg0})", "supplied Slot"),
        ("f(z=${arg2},x=${arg0},again=${arg0})", "supplied Slot"),
    ):

        @realizes(FunctionCall)
        class Unsafe:
            supports = claimed
            template = source_template

        registry = RealizationRegistry("test", (Unsafe,))
        with pytest.raises(ConstructError, match=problem):
            Composer(registry).layout(node)

    @realizes(FunctionCall)
    class Safe:
        supports = claimed
        template = "f(z=${arg2},x=${arg0})"

    @realizes(Literal)
    class Number:
        variant = "integer"
        render = lambda node, _: repr(node.value)

    registry = RealizationRegistry("test", (Safe, Number))
    assert Composer(registry).source(node) == "f(z=4,x=1)\n"


def test_realized_nested_calls_preserve_executed_argument_order_and_default() -> None:
    source = """
def next_value(x: int) -> int:
    return x
def f(x: int, y: int = 5, z: int = 6) -> int:
    return x * 100 + y * 10 + z
result: int = f(z=next_value(3), x=next_value(1))
"""
    outer = PythonFrontend().parse(source).body.children[-1].value
    assert isinstance(outer, FunctionCall)
    assert outer.argument_evaluation_order == (2, 0, 1)
    assert outer.omitted_arguments == (1,)

    def choose(node: Construct, _: EmitContext) -> str:
        assert isinstance(node, FunctionCall)
        if node.signature.name == "f":
            return "f(z=${arg2}, x=${arg0})"
        assert node.signature.name == "next_value"
        return "next_value(${arg0})"

    @realizes(FunctionCall)
    class Calls:
        supports = (
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
        )
        render = choose

    @realizes(Literal)
    class Numbers:
        variant = "integer"
        render = lambda node, _: repr(node.value)

    rendered = Composer(RealizationRegistry("python-test", (Calls, Numbers))).source(
        outer
    )
    assert rendered == "f(z=next_value(3), x=next_value(1))\n"
    visited: list[int] = []

    def next_value(x: int) -> int:
        visited.append(x)
        return x

    def f(x: int, y: int = 5, z: int = 6) -> int:
        return x * 100 + y * 10 + z

    assert eval(rendered, {"f": f, "next_value": next_value}) == 153
    assert visited == [3, 1]


def test_combined_dispatch_and_argument_layouts_are_composed() -> None:
    """Trace layouts expose each distinct call form without flattening Model."""
    from pyinto.constructs import ClassReference, Reference

    calls = _calls()

    def choose_method(node: Construct, _: EmitContext) -> str:
        assert isinstance(node, MethodCall)
        if node.dispatch is MethodDispatch.SUPER:
            assert node.lookup_start is not None
            return (
                f"super@{node.lookup_start.identity.name}[${{receiver}}]"
                ".${method}(z=${arg2},x=${arg0})"
            )
        return "virtual[${receiver}].${method}(z=${arg2},x=${arg0})"

    @realizes(MethodCall)
    class Methods:
        supports = (
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
            "method.dispatch.virtual",
            "method.dispatch.super",
            "method.lookup.lexical_base",
        )
        render = choose_method

    @realizes(InstanceCreation)
    class Constructors:
        supports = (
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
        )
        template = "${class_name}(z=${arg2},x=${arg0})"

    @realizes(ClassMethodCall)
    class ClassCalls:
        supports = (
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
            "class_receiver.runtime_identity",
        )
        template = "${class_source}.${method}(z=${arg2},x=${arg0})"

    @realizes(ClassReceiverCreation)
    class Factories:
        supports = (
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
            "class_receiver.runtime_identity",
        )
        template = "${receiver}(z=${arg2},x=${arg0})"

    @realizes(Reference)
    class References:
        template = "${name}"

    @realizes(ClassReference)
    class Classes:
        template = "${class_name}"

    @realizes(Literal)
    class Numbers:
        variant = "integer"
        render = lambda node, _: repr(node.value)

    registry = RealizationRegistry(
        "trace",
        (Methods, Constructors, ClassCalls, Factories, References, Classes, Numbers),
    )
    assert Composer(registry).source(calls["super"]) == (
        "super@Base[self].total(z=z,x=x)\n"
    )
    assert Composer(registry).source(calls["virtual"]) == (
        "virtual[obj].total(z=9,x=5)\n"
    )
    assert Composer(registry).source(calls["new"]) == "Derived(z=8,x=4)\n"
    assert Composer(registry).source(calls["class"]) == "Derived.create(z=11,x=6)\n"
    assert Composer(registry).source(calls["factory"]) == "cls(z=z,x=x)\n"


def test_templateplan_materializes_supplied_arguments_in_source_order() -> None:
    """A Target can materialize arguments before binding them positionally."""
    from pyinto.realizations.layout import TemplatePlan

    source = """
def next_value(x: int) -> int:
    return x
def f(x: int, y: int = 5, z: int = 6) -> int:
    return x * 100 + y * 10 + z
result: int = f(z=next_value(3), x=next_value(1))
"""
    outer = PythonFrontend().parse(source).body.children[-1].value
    assert isinstance(outer, FunctionCall)

    def plan(node: Construct, ctx: EmitContext) -> str | TemplatePlan:
        assert isinstance(node, FunctionCall)
        if node.signature.name == "next_value":
            return "next_value(${arg0})"
        first = ctx.fresh("first")
        second = ctx.fresh("second")
        return TemplatePlan(
            f"{first} = ${{evaluate_z}}\n"
            f"{second} = ${{evaluate_x}}\n"
            f"result = f({second}, ${{default_y}}, {first})",
            {
                "evaluate_z": node.arguments[2],
                "evaluate_x": node.arguments[0],
                "default_y": node.arguments[1],
            },
        )

    @realizes(FunctionCall)
    class Calls:
        supports = (
            "call.arguments.bound",
            "call.arguments.reordered",
            "call.arguments.left_to_right",
            "call.defaults.omitted",
        )
        render = plan

    @realizes(Literal)
    class Numbers:
        variant = "integer"
        render = lambda node, _: repr(node.value)

    output = Composer(RealizationRegistry("python-test", (Calls, Numbers))).source(
        outer
    )
    assert output == (
        "sk_first_0 = next_value(3)\n"
        "sk_second_1 = next_value(1)\n"
        "result = f(sk_second_1, 5, sk_first_0)\n"
    )
    visited: list[int] = []

    def next_value(x: int) -> int:
        visited.append(x)
        return x

    def f(x: int, y: int = 5, z: int = 6) -> int:
        return x * 100 + y * 10 + z

    namespace: dict[str, object] = {"f": f, "next_value": next_value}
    exec(output, namespace)  # noqa: S102 (controlled, generated test source)
    assert namespace["result"] == 153
    assert visited == [3, 1]
