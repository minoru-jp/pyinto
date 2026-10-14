"""Conservative checks for call layouts expressed through direct Model Slots.

These checks cover only simple string templates (including selectors returning a
string). More expressive TemplatePlan slots require target-specific tests: an
arbitrary piece of target code cannot be proved correct by inspecting holes.
"""

from __future__ import annotations

from collections import Counter

from pyinto.constructs import (
    Arithmetic,
    Call,
    ClassMethodCall,
    ClassReceiverCreation,
    Comparison,
    Construct,
    ConstructError,
    FloatingArithmetic,
    FloatingComparison,
    FunctionCall,
    FunctionValueCall,
    InstanceCreation,
    IntrinsicCall,
    MethodCall,
    StringComparison,
    StringConcat,
    StringContains,
    StringElement,
    StringRepeat,
)
from pyinto.realizations.layout import PLACEHOLDER

_BOUND_CALLS = (
    FunctionCall,
    InstanceCreation,
    ClassMethodCall,
    ClassReceiverCreation,
    MethodCall,
)


def check_direct_call_slots(node: Construct, source: str) -> None:
    """Ensure supplied expressions appear once, in source-evaluation order.

    Omitted scalar defaults may be emitted or elided by the Target; their
    placement is not part of the supplied-expression evaluation sequence.
    This check does *not* prove a target-language template evaluates Slots
    in text order, preserves implicit receiver dispatch,
    nor that it binds arguments correctly. Those obligations remain with its
    Realization and integration tests.
    """
    if not isinstance(node, _BOUND_CALLS):
        return
    holes = PLACEHOLDER.findall(source)
    counts = Counter(holes)
    supplied = tuple(
        f"arg{index}"
        for index in node.argument_evaluation_order
        if index not in node.omitted_arguments
    )
    for name in supplied:
        if counts[name] != 1:
            raise ConstructError(
                f"Call layout must use supplied Slot ${{{name}}} exactly once"
            )
    actual_order = tuple(hole for hole in holes if hole in supplied)
    if actual_order != supplied:
        raise ConstructError(
            "Call layout changes source argument evaluation order: "
            f"expected {supplied}, got {actual_order}"
        )


# For a direct string template, the Model's expression children must not
# disappear or be duplicated. This inspects text order only, not Target runtime
# order: a C arithmetic expression with two function calls is still unsafe.
_ORDERED_PARTS: dict[type[Construct], tuple[str, str]] = {
    Arithmetic: ("left", "right"),
    Comparison: ("left", "right"),
    FloatingArithmetic: ("left", "right"),
    FloatingComparison: ("left", "right"),
    StringConcat: ("left", "right"),
    StringRepeat: ("left", "right"),
    StringComparison: ("left", "right"),
    StringContains: ("needle", "haystack"),
    StringElement: ("source", "index"),
}


def check_direct_expression_slots(node: Construct, source: str) -> None:
    """Require once-used, text-ordered value Slots for simple Templates.

    A TemplatePlan may provide derived Slots implementing an alternative layout,
    and is deliberately not inspected by this conservative check.
    """
    expected = _ORDERED_PARTS.get(type(node))
    if isinstance(node, FunctionValueCall):
        expected = ("callee", *(f"arg{i}" for i in range(len(node.arguments))))
    elif isinstance(node, IntrinsicCall):
        expected = (
            *(("receiver",) if node.receiver is not None else ()),
            *(f"arg{i}" for i in range(len(node.arguments))),
        )
    elif isinstance(node, Call):
        expected = tuple(f"arg{i}" for i in range(len(node.arguments)))
    if expected is None:
        return
    holes = PLACEHOLDER.findall(source)
    counts = Counter(holes)
    if any(counts[name] != 1 for name in expected):
        raise ConstructError(
            f"Direct expression layout must use each Model Slot once: {expected}"
        )
    observed = tuple(hole for hole in holes if hole in expected)
    if observed != expected:
        raise ConstructError(
            "Direct expression layout changes Model evaluation sequence: "
            f"expected {expected}, got {observed}"
        )
