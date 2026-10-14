"""SDD 21: Boolean constants, first-class None, and typed conditional values.

New operations are Model-only and do not reinterpret older Literal/Return or
create implicit Optional, Python truthiness, or Target runtime support.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Assign,
    BooleanLiteral,
    BooleanNot,
    BooleanOperation,
    CallableType,
    ConditionalExpression,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    Initialize,
    InstanceType,
    ListType,
    Literal,
    NoneLiteral,
    Reference,
    Return,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def _expressions(source: str) -> list[object]:
    program = PythonFrontend().parse(source)
    return [
        s.value for s in program.body.children if isinstance(s, (Initialize, Assign))
    ]


def _has_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (tuple, list)):
        return any(_has_ast(part) for part in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_has_ast(getattr(value, fld.name)) for fld in fields(value))
    return False


@pytest.mark.parametrize("value", [True, False])
def test_cst_042_boolean_literals_are_new_immutable_value_nodes(value: bool) -> None:
    literal = BooleanLiteral(value)
    assert literal.kind is ValueKind.BOOLEAN
    assert literal.value_type == ValueType(ValueKind.BOOLEAN)
    assert literal.variant() == ("true" if value else "false")
    assert literal.parts() == {}
    with pytest.raises(FrozenInstanceError):
        literal.value = not value  # type: ignore[misc]
    with pytest.raises(ValueError, match="integer or string"):
        Literal(value)


@pytest.mark.parametrize("bad", [1, 0, "True", None, 1.0])
def test_cst_042_boolean_literal_strictly_requires_bool(bad: object) -> None:
    with pytest.raises(ConstructError, match="True or False"):
        BooleanLiteral(bad)  # type: ignore[arg-type]


def test_cst_043_none_literal_is_a_value_not_missing_return() -> None:
    none_value = NoneLiteral()
    assert none_value.kind is ValueKind.NONE
    assert none_value.value_type == ValueType(ValueKind.NONE)
    assert none_value.parts() == {}
    assert Return(none_value).parts() == {"value": none_value}
    assert Return().parts() == {}
    with pytest.raises(ValueError, match="integer or string"):
        Literal(None)  # type: ignore[arg-type]


def test_cst_044_conditional_keeps_branch_order_and_shape() -> None:
    condition = BooleanLiteral(True)
    yes, no = Literal(1), Literal(2)
    expr = ConditionalExpression(condition, yes, no, ValueType(ValueKind.INTEGER))
    assert expr.kind is ValueKind.INTEGER
    assert expr.parts() == {
        "condition": condition,
        "when_true": yes,
        "when_false": no,
    }
    assert expr.value_type == ValueType(ValueKind.INTEGER)
    with pytest.raises(FrozenInstanceError):
        expr.condition = BooleanLiteral(False)  # type: ignore[misc]


@pytest.mark.parametrize(
    "condition, yes, no, result, diagnostic",
    [
        (Literal(1), Literal(2), Literal(3), ValueType(ValueKind.INTEGER), "Boolean"),
        (
            BooleanLiteral(True),
            Literal(2),
            Literal("a"),
            ValueType(ValueKind.INTEGER),
            "branch type",
        ),
        (
            BooleanLiteral(True),
            NoneLiteral(),
            Literal(3),
            ValueType(ValueKind.INTEGER),
            "branch type",
        ),
        (
            BooleanLiteral(True),
            Literal(1),
            Literal(2),
            ValueType(ValueKind.STRING),
            "branch type",
        ),
    ],
)
def test_cst_044_invalid_conditions_and_branches_fail_at_construction(
    condition: object, yes: object, no: object, result: ValueType, diagnostic: str
) -> None:
    with pytest.raises(ConstructError, match=diagnostic):
        ConditionalExpression(condition, yes, no, result)  # type: ignore[arg-type]


def test_cst_044_nested_result_types_propagate_without_inference() -> None:
    fn_type = CallableType(
        (ValueType(ValueKind.INTEGER),), ValueType(ValueKind.BOOLEAN)
    )
    result_type = ValueType(ValueKind.FUNCTION, callable_type=fn_type)
    from pyinto.constructs import Symbol

    f = Reference(
        Symbol(
            "f",
            ValueType(ValueKind.FUNCTION, callable_type=fn_type),
            "Callable[[int], bool]",
        )
    )
    g = Reference(
        Symbol(
            "g",
            ValueType(ValueKind.FUNCTION, callable_type=fn_type),
            "Callable[[int], bool]",
        )
    )
    expr = ConditionalExpression(BooleanLiteral(True), f, g, result_type)
    assert expr.kind is ValueKind.FUNCTION
    assert expr.callable_type is fn_type

    list_type = ListType(ValueType(ValueKind.INTEGER))
    xs = Reference(
        Symbol("xs", ValueType(ValueKind.LIST, list_type=list_type), "list[int]")
    )
    ys = Reference(
        Symbol("ys", ValueType(ValueKind.LIST, list_type=list_type), "list[int]")
    )
    selected = ConditionalExpression(
        BooleanLiteral(False), xs, ys, ValueType(ValueKind.LIST, list_type=list_type)
    )
    assert selected.list_type == list_type


def test_frt_035_boolean_constants_support_logic_and_control_flow() -> None:
    program = PythonFrontend().parse(
        "flag: bool = True\n"
        "flag = not False\n"
        "if flag and True:\n"
        "    print('yes')\n"
        "while False:\n"
        "    print('no')\n"
    )
    declare, assign, branch, loop = program.body.children
    assert isinstance(declare.value, BooleanLiteral)
    assert declare.value.value is True
    assert isinstance(assign.value, BooleanNot)
    assert isinstance(assign.value.operand, BooleanLiteral)
    assert isinstance(branch.condition, BooleanOperation)
    assert isinstance(branch.condition.operands[-1], BooleanLiteral)
    assert isinstance(loop.condition, BooleanLiteral)
    assert not _has_ast(program)


def test_frt_036_none_is_general_value_in_object_and_any_contexts() -> None:
    program = PythonFrontend().parse(
        "from typing import Any\na: object = None\na = 1\na = None\nb: Any = None\n"
    )
    a, _, reassign, b = program.body.children
    assert isinstance(a.value, NoneLiteral)
    assert isinstance(reassign.value, NoneLiteral)
    assert isinstance(b.value, NoneLiteral)


def test_frt_036_none_can_be_passed_and_returned_as_a_value() -> None:
    program = PythonFrontend().parse(
        "def passthrough(value: object) -> object:\n"
        "    return value\n"
        "def nothing() -> object:\n"
        "    return None\n"
        "def old_style() -> None:\n"
        "    return None\n"
        "result: object = passthrough(None)\n"
    )
    fn = program.body.children[1]
    assert isinstance(fn, FunctionDefinition)
    returned = fn.body.children[0]
    assert isinstance(returned, Return)
    assert isinstance(returned.value, NoneLiteral)
    old_style = program.body.children[2]
    assert isinstance(old_style.body.children[0], Return)
    assert old_style.body.children[0].value is None
    call = program.body.children[3].value
    assert isinstance(call, FunctionCall)
    assert isinstance(call.arguments[0], NoneLiteral)


def test_frt_037_conditional_with_literal_and_name_operands() -> None:
    yes, no = _expressions(
        "flag: bool = True\na: int = 1 if flag else 2\nb: int = a if not False else 3\n"
    )[1:]
    assert isinstance(yes, ConditionalExpression)
    assert isinstance(yes.condition, Reference)
    assert isinstance(yes.when_true, Literal)
    assert isinstance(yes.when_false, Literal)
    assert isinstance(no, ConditionalExpression)
    assert isinstance(no.condition, BooleanNot)
    assert no.value_type == ValueType(ValueKind.INTEGER)


def test_frt_037_conditional_preserves_only_one_selected_branch_contract() -> None:
    program = PythonFrontend().parse(
        "def left() -> int:\n"
        "    return 1\n"
        "def right() -> int:\n"
        "    return 2\n"
        "result: int = left() if True else right()\n"
    )
    conditional = program.body.children[-1].value
    assert isinstance(conditional, ConditionalExpression)
    assert isinstance(conditional.when_true, FunctionCall)
    assert isinstance(conditional.when_false, FunctionCall)
    assert conditional.when_true.signature.name == "left"
    assert conditional.when_false.signature.name == "right"


def test_frt_037_conditional_nested_shapes_with_explicit_expected_type() -> None:
    program = PythonFrontend().parse(
        "xs: list[int] = [1]\n"
        "ys: list[int] = [2]\n"
        "chosen: list[int] = xs if True else ys\n"
        "option: object = None if False else 1\n"
    )
    selected = program.body.children[2].value
    assert selected.list_type == ListType(ValueType(ValueKind.INTEGER))
    other = program.body.children[-1].value
    assert isinstance(other, ConditionalExpression)
    assert other.kind is ValueKind.OBJECT
    assert isinstance(other.when_true, NoneLiteral)
    assert isinstance(other.when_false, Literal)


def test_frt_037_conditional_nominal_subtyping_uses_contextual_type() -> None:
    program = PythonFrontend().parse(
        "class Base:\n"
        "    def __init__(self) -> None:\n"
        "        self.number: int = 1\n"
        "class Child(Base):\n"
        "    def __init__(self) -> None:\n"
        "        super().__init__()\n"
        "base: Base = Base()\n"
        "child: Child = Child()\n"
        "value: Base = child if True else base\n"
    )
    expr = program.body.children[-1].value
    assert isinstance(expr, ConditionalExpression)
    assert expr.kind is ValueKind.INSTANCE
    assert expr.instance_type == InstanceType("Base")


@pytest.mark.parametrize(
    "source, expected_error",
    [
        ("x: int = None", "Annotated type"),
        ("x: bool = 1", "Annotated type"),
        ("x: int = True", "Annotated type"),
        ("x: None = None", "None is not a variable type"),
        ("x: list[None] = []", "Unsupported list element type"),
        ("x: dict[str, None] = {}", "values require"),
        ("x: list[int] = [None]", "type mismatch"),
        ("x: int = 1 if True else 'str'", "branch type mismatch"),
        ("x: int = 1 if 1 else 2", "Boolean condition"),
        ("x: int = None if True else 2", "branch type mismatch"),
        ("x: int = 1 if True else None", "branch type mismatch"),
        ("x: bool = 1 and True", "Boolean operation requires"),
        ("x: bool = not 1", "Boolean not requires"),
        ("x: int = 1.0 if True else 2", "branch type mismatch"),
        ("def f() -> int:\n    return None", "Return type mismatch"),
        (
            "def f() -> None:\n    return 3 if True else 4",
            "None-returning function cannot return a value",
        ),
    ],
)
def test_frt_038_rejected_forms_are_explicit(source: str, expected_error: str) -> None:
    with pytest.raises(UnsupportedPython, match=expected_error):
        PythonFrontend().parse(source)


@pytest.mark.parametrize(
    "source, node_name",
    [
        ("x: bool = True", "BooleanLiteral"),
        ("x: object = None", "NoneLiteral"),
        ("x: int = 1 if True else 2", "ConditionalExpression"),
    ],
)
def test_frt_038_missing_realization_is_explicit_and_model_unchanged(
    source: str, node_name: str
) -> None:
    model = PythonFrontend().parse(source)
    snapshot = repr(model)
    with pytest.raises(ConstructError, match=f"No 'c' realization for {node_name}"):
        realize(model, realizations=c_bindings())
    assert repr(model) == snapshot
    assert not _has_ast(model)
