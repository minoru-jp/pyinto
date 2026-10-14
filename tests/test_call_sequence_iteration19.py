"""Iteration 19: source-order is a Model obligation even without keywords.

A Target may need to introduce temporaries to honor the obligation. Merely
placing ${arg0}, ${arg1} in textual order cannot guarantee execution order for
all targets. These tests check admission, not Target semantic equivalence.
"""

from __future__ import annotations

import pytest

from pyinto.constructs import ConstructError, FunctionCall
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import (
    realizes,
    render,
    requires,
    supports,
    template,
)
from tests.test_call_realization_iteration16 import _calls


def _call(expression: str) -> FunctionCall:
    source = (
        "def g() -> int:\n    return 1\n"
        "def h() -> int:\n    return 2\n"
        "def f(x: int, y: int = 3) -> int:\n    return x + y\n"
        f"result: int = {expression}\n"
    )
    node = PythonFrontend().parse(source).body.children[-1].value
    assert isinstance(node, FunctionCall)
    return node


def test_positional_call_also_requires_ordered_evaluation() -> None:
    two = _call("f(g(), h())")
    assert two.argument_evaluation_order == (0, 1)
    assert required_contracts(two) == {
        "call.arguments.bound",
        "call.arguments.left_to_right",
    }
    assert required_contracts(_call("f(g())")) == {
        "call.arguments.bound",
        "call.defaults.omitted",
    }


def test_rebinding_and_expression_order_are_independent() -> None:
    call = _call("f(y=h(), x=g())")
    assert required_contracts(call) == {
        "call.arguments.bound",
        "call.arguments.left_to_right",
        "call.arguments.reordered",
    }
    assert "call.arguments.reordered" not in required_contracts(_call("f(g(), h())"))
    # Do not classify a default filled in by Frontend as a supplied expression.
    assert "call.arguments.left_to_right" not in required_contracts(_call("f(g())"))


def test_plain_template_is_rejected_before_render_for_unordered_target() -> None:
    call = _call("f(g(), h())")
    rendered: list[object] = []

    @realizes(FunctionCall)
    class NoOrderGuarantee:
        requires @= "should_not_be_collected.h"
        supports @= ("call.arguments.bound",)
        render @= lambda node, _: (rendered.append(node), "f(${arg0}, ${arg1})")[1]

    bindings = RealizationRegistry("unordered-target", (NoOrderGuarantee,))
    context = EmitContext(bindings)
    with pytest.raises(ConstructError, match="call.arguments.left_to_right"):
        bindings.recipe(call, context)
    assert not context.headers and not rendered

    # Claiming support is an explicit Target responsibility, not a proof.
    @realizes(FunctionCall)
    class DeclaresOrder:
        supports @= ("call.arguments.bound", "call.arguments.left_to_right")
        template @= "f(${arg0}, ${arg1})"

    supported = RealizationRegistry("target-contract-declaration", (DeclaresOrder,))
    assert supported.recipe(call, EmitContext(supported)).supports >= {
        "call.arguments.left_to_right"
    }


def test_all_five_bound_call_forms_require_order_even_without_reordering() -> None:
    calls = _calls()
    assert len(calls) == 5
    assert all(
        "call.arguments.left_to_right" in required_contracts(c) for c in calls.values()
    )
    # The new rule is Target-agnostic and has no impact on ordinary Python
    # Frontend parsing or existing basic C/Python Pack entry selection.
