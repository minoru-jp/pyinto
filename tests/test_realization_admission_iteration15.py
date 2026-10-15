"""Iteration 15: admission checks before any recipe renders/changes context."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    ClassDefinition,
    ConstructError,
    FunctionCall,
    InstanceCreation,
    MethodCall,
    MethodDispatch,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    naming,
    realizes,
)
from tests.test_keyword_arguments_phase25 import CLASS, FUNCTION


def _function_call(expression: str = "f(1, 2, 3)") -> FunctionCall:
    parsed = PythonFrontend().parse(FUNCTION + f"result: int = {expression}")
    node = parsed.body.children[-1].value
    assert isinstance(node, FunctionCall)
    return node


def _method_calls() -> tuple[MethodCall, MethodCall]:
    parsed = PythonFrontend().parse(
        CLASS + "obj: Base = Derived(2, 4)\nresult: int = obj.total(10, 20)"
    )
    derived = parsed.body.children[1]
    assert isinstance(derived, ClassDefinition)
    direct = parsed.body.children[-1].value
    super_call = derived.methods[1].body.children[0].value
    assert isinstance(direct, MethodCall)
    assert isinstance(super_call, MethodCall)
    assert direct.dispatch is MethodDispatch.VIRTUAL
    assert super_call.dispatch is MethodDispatch.SUPER
    return direct, super_call


def test_call_obligations_are_derived_from_instance_not_variant() -> None:
    positional = _function_call()
    reordered = _function_call("f(z=3, x=1, y=2)")
    assert positional.variant() == reordered.variant()
    assert required_contracts(positional) == {
        "call.arguments.bound",
        "call.arguments.left_to_right",
    }
    assert required_contracts(reordered) == {
        "call.arguments.bound",
        "call.arguments.left_to_right",
        "call.arguments.reordered",
    }
    constructor = PythonFrontend().parse(CLASS + "obj: Base = Derived(y=4, x=2)")
    created = constructor.body.children[-1].value
    assert isinstance(created, InstanceCreation)
    assert "call.arguments.reordered" in required_contracts(created)


def test_method_dispatch_cannot_be_silently_ignored() -> None:
    direct, super_call = _method_calls()
    assert direct.variant() == super_call.variant() == "default"

    @realizes(MethodCall)
    class Unsafe:
        template = "${receiver}.${method}()"

    registry = RealizationRegistry("test", (Unsafe,))
    with pytest.raises(ConstructError, match=r"method.dispatch.virtual"):
        registry.recipe(direct, EmitContext(registry))
    with pytest.raises(ConstructError, match=r"method.dispatch.super"):
        registry.recipe(super_call, EmitContext(registry))

    @realizes(MethodCall)
    class VirtualOnly:
        template = "${receiver}.${method}()"
        supports = (
            "call.arguments.bound",
            "call.arguments.left_to_right",
            "method.dispatch.virtual",
        )

    registry = RealizationRegistry("test", (VirtualOnly,))
    assert registry.recipe(direct, EmitContext(registry)).template is not None
    with pytest.raises(ConstructError, match=r"method.dispatch.super"):
        registry.recipe(super_call, EmitContext(registry))


def test_reordered_arguments_and_omission_require_explicit_support() -> None:
    positional = _function_call()
    reordered = _function_call("f(z=3, x=1, y=2)")

    @realizes(FunctionCall)
    class BoundOnly:
        template = "${arg0},${arg1},${arg2}"
        supports = ("call.arguments.bound",)

    registry = RealizationRegistry("test", (BoundOnly,))
    with pytest.raises(ConstructError, match="call.arguments.left_to_right"):
        registry.recipe(positional, EmitContext(registry))

    @realizes(FunctionCall)
    class OrderedOnly:
        template = "${arg0},${arg1},${arg2}"
        supports = ("call.arguments.bound", "call.arguments.left_to_right")

    registry = RealizationRegistry("test", (OrderedOnly,))
    assert registry.recipe(positional, EmitContext(registry)).template is not None
    with pytest.raises(ConstructError, match="call.arguments.reordered"):
        registry.recipe(reordered, EmitContext(registry))

    # Omissions are a different obligation from reordering.
    source = """\ndef f(x: int, y: int = 2) -> int:
    return x + y
result: int = f(1)
"""
    defaulted = PythonFrontend().parse(source).body.children[-1].value
    assert isinstance(defaulted, FunctionCall)
    assert "call.defaults.omitted" in required_contracts(defaulted)

    @realizes(FunctionCall)
    class AcceptsDefaults:
        template = "${arg0},${arg1}"
        supports = ("call.arguments.bound", "call.defaults.omitted")

    registry = RealizationRegistry("test", (AcceptsDefaults,))
    assert registry.recipe(defaulted, EmitContext(registry)).template is not None


def test_admission_happens_before_headers_and_renderer() -> None:
    rendered = []

    @realizes(FunctionCall)
    class Unsafe:
        requires = ("danger.h",)
        render = lambda node, ctx: (rendered.append("called"), "${arg0}")[1]

    registry = RealizationRegistry("test", (Unsafe,))
    ctx = EmitContext(registry)
    with pytest.raises(ConstructError, match="call.arguments.bound"):
        registry.recipe(_function_call(), ctx)
    assert ctx.headers == set()
    assert rendered == []

    with pytest.raises(ConstructError, match="call.arguments.bound"):
        Composer(registry).layout(_function_call())


def test_support_declaration_is_validated() -> None:
    @realizes(FunctionCall)
    class NotNamespaced:
        template = "${arg0}"
        supports = ("every_semantic_contract",)

    with pytest.raises(ValueError, match="unique namespaced"):
        RealizationRegistry("test", (NotNamespaced,))

    @realizes(FunctionCall)
    class Duplicate:
        template = "${arg0}"
        supports = ("call.arguments.bound", "call.arguments.bound")

    with pytest.raises(ValueError, match="unique namespaced"):
        RealizationRegistry("test", (Duplicate,))

    @naming
    class WrongRole:
        supports = ("call.arguments.bound",)

    with pytest.raises(ValueError, match="supports belongs"):
        RealizationRegistry("test", (WrongRole,))


def test_unknown_names_are_not_wildcards_and_standard_targets_still_work() -> None:
    from pyinto import realize
    from tests.support.c_realizer import c_bindings
    from tests.support.python_realizer.pack import python_bindings

    @realizes(FunctionCall)
    class NoWildcard:
        template = "${arg0},${arg1},${arg2}"
        supports = ("call.arguments.*",)

    with pytest.raises(ValueError, match="unique namespaced"):
        RealizationRegistry("test", (NoWildcard,))

    program = PythonFrontend().parse('x: int = 1\nprint("still works")')
    assert 'puts("still works")' in realize(program, realizations=c_bindings())
    assert "print('still works')" in realize(program, realizations=python_bindings())
