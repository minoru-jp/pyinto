"""Iteration 23: declared evaluation obligations and conservative direct Slots.

Textual Slot order is *not* assumed to be runtime evaluation order in C.
"""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    Arithmetic,
    Call,
    CallableType,
    Comparison,
    ConstructError,
    FunctionValueCall,
    Literal,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import required_contracts
from pyinto.interfaces import builtins as builtin
from pyinto.realizations.registry import Composer, EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def test_binary_obligations_do_not_depend_on_effect_inference() -> None:
    for node in (
        Comparison(Literal(1), "<", Literal(2)),
        Arithmetic(Literal(1), "+", Literal(2)),
    ):
        assert required_contracts(node) == {"evaluation.operands.left_to_right"}
    assert required_contracts(Comparison(Literal(1), "==", Literal(1))) == {
        "evaluation.operands.left_to_right"
    }


def test_unbound_mapped_call_and_function_value_order() -> None:
    print_call = Call(Symbol("print", None), (Literal(1), Literal(2)))
    assert required_contracts(print_call) == {"call.arguments.left_to_right"}
    assert required_contracts(Call(Symbol("print", None), (Literal(1),))) == set()
    integer = ValueType(ValueKind.INTEGER)
    callable_shape = CallableType((integer, integer), integer)
    fn = Reference(
        Symbol(
            "f",
            ValueType(ValueKind.FUNCTION, callable_type=callable_shape),
            "Callable[[int, int], int]",
        )
    )
    call = FunctionValueCall(fn, (Literal(1), Literal(2)))
    assert required_contracts(call) == {
        "call.arguments.left_to_right",
        "function_value.callee_before_arguments",
    }

    @realizes(FunctionValueCall)
    class Missing:
        template = "${callee}(${arg0},${arg1})"

    reg = RealizationRegistry("probe", (Missing,))
    with pytest.raises(ConstructError, match="callee_before_arguments"):
        reg.recipe(call, EmitContext(reg))

    @realizes(FunctionValueCall)
    class Ready:
        template = "${callee}(${arg0}, ${arg1})"
        supports = (
            "call.arguments.left_to_right",
            "function_value.callee_before_arguments",
        )

    @realizes(builtin.PrintCall)
    class BadPrint:
        template = "print(${arg0},${arg1})"

    with pytest.raises(ConstructError, match="call.arguments.left_to_right"):
        Composer(RealizationRegistry("probe", (BadPrint,))).layout(print_call)
    registry = RealizationRegistry("probe", (Ready,))
    assert registry.recipe(call, EmitContext(registry)).template is not None


@pytest.mark.parametrize(
    ("template_source", "match"),
    [
        ("(${left})", "each Model Slot once"),
        ("(${left} + ${left} + ${right})", "each Model Slot once"),
        ("(${right} + ${left})", "evaluation sequence"),
    ],
)
def test_string_binary_slots_cannot_drop_duplicate_or_reorder(
    template_source: str, match: str
) -> None:
    @realizes(Arithmetic)
    class Broken:
        supports = ("evaluation.operands.left_to_right",)
        template = template_source

    node = Arithmetic(Literal(1), "+", Literal(2))
    with pytest.raises(ConstructError, match=match):
        Composer(RealizationRegistry("probe", (Broken,))).layout(node)


def test_mapped_and_indirect_call_slots_must_be_present_once_in_order() -> None:
    print_call = Call(Symbol("print", None), (Literal(1), Literal(2)))

    @realizes(builtin.PrintCall)
    class Reversed:
        supports = ("call.arguments.left_to_right",)
        template = "print(${arg1}, ${arg0})"

    with pytest.raises(ConstructError, match="evaluation sequence"):
        Composer(RealizationRegistry("probe", (Reversed,))).layout(print_call)

    @realizes(builtin.PrintCall)
    class Missing:
        supports = ("call.arguments.left_to_right",)
        template = "print(${arg0})"

    with pytest.raises(ConstructError, match="each Model Slot once"):
        Composer(RealizationRegistry("probe", (Missing,))).layout(print_call)


def test_indirect_callee_slot_cannot_be_dropped_or_repeated() -> None:
    from tests.support.python_realizer.pack import PYTHON_DECLARATIONS

    integer = ValueType(ValueKind.INTEGER)
    callable_shape = CallableType((integer,), integer)
    receiver = Reference(
        Symbol(
            "fn",
            ValueType(ValueKind.FUNCTION, callable_type=callable_shape),
            "Callable[[int], int]",
        )
    )
    node = FunctionValueCall(receiver, (Literal(3),))

    @realizes(FunctionValueCall)
    class DuplicateCallee:
        supports = ("function_value.callee_before_arguments",)
        template = "${callee}(${arg0}) + ${callee}(${arg0})"

    with pytest.raises(ConstructError, match="each Model Slot once"):
        Composer(
            RealizationRegistry("python", (*PYTHON_DECLARATIONS, DuplicateCallee))
        ).layout(node)

    @realizes(FunctionValueCall)
    class WrongOrder:
        supports = ("function_value.callee_before_arguments",)
        template = "(${arg0}, ${callee})"

    with pytest.raises(ConstructError, match="evaluation sequence"):
        Composer(
            RealizationRegistry("python", (*PYTHON_DECLARATIONS, WrongOrder))
        ).layout(node)


def test_c_comparison_keeps_safe_leaf_bindings_and_rejects_compounds() -> None:
    safe = Comparison(
        Reference(Symbol("a", ValueType(ValueKind.INTEGER), "int")), "<", Literal(3)
    )
    code = Composer(c_bindings()).source(safe)
    assert "a < 3LL" in code
    assert "a < 3" in Composer(python_bindings()).source(safe)
    compound = Comparison(
        Arithmetic(Literal(1), "+", Literal(2)),
        "<",
        Arithmetic(Literal(3), "+", Literal(4)),
    )
    with pytest.raises(
        ConstructError, match="cannot guarantee operand evaluation order"
    ):
        Composer(c_bindings()).layout(compound)


def test_ordered_comparison_requires_explicit_support() -> None:
    @realizes(Comparison)
    class Broken:
        template = "(${left} ${op} ${right})"

    node = Comparison(Literal(1), "<", Literal(2))
    reg = RealizationRegistry("probe", (Broken,))
    with pytest.raises(ConstructError, match="evaluation.operands.left_to_right"):
        reg.recipe(node, EmitContext(reg))
