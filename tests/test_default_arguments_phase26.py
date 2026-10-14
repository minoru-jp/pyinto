"""Phase 26: scalar-only declared defaults, not Python's general default semantics."""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    BooleanLiteral,
    ConstructError,
    FloatingLiteral,
    FunctionCall,
    FunctionSignature,
    InstanceCreation,
    Literal,
    MethodCall,
    NoneLiteral,
    Parameter,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def body(source: str):
    return PythonFrontend().parse(source).body.children


def test_scalar_defaults_retained_in_signature_and_parameter_parts() -> None:
    tree = body("""
def f(a: int, b: str = "ok", c: bool = False, d: float = -1.5, e: object = None) -> int:
    return a
result: int = f(8)
""")
    definition, assign = tree
    signature = definition.signature
    assert signature.parameter_defaults == (
        None,
        Literal("ok"),
        BooleanLiteral(False),
        FloatingLiteral(-1.5),
        NoneLiteral(),
    )
    params = definition.parts()["parameters"]
    assert len(params) == 5
    assert isinstance(params[0], Parameter)
    assert "default" not in params[0].parts()
    assert params[-1].parts()["default"] == NoneLiteral()
    call = assign.value
    assert isinstance(call, FunctionCall)
    assert call.omitted_arguments == (1, 2, 3, 4)
    assert call.arguments == (Literal(8), *signature.parameter_defaults[1:])
    assert call.supplied_evaluation_arguments == (Literal(8),)
    assert call.argument_evaluation_order == (0, 1, 2, 3, 4)


def test_omitted_default_is_distinct_from_explicit_none() -> None:
    definition, a, b = body("""
def f(x: object = None) -> object:
    return x
first: object = f()
second: object = f(None)
""")
    assert definition.signature.defaults_by_parameter == (NoneLiteral(),)
    assert a.value.omitted_arguments == (0,)
    assert b.value.omitted_arguments == ()
    assert a.value.arguments == b.value.arguments
    assert a.value.supplied_evaluation_arguments == ()
    assert b.value.supplied_evaluation_arguments == (NoneLiteral(),)


def test_combined_keywords_and_defaults_keep_source_order() -> None:
    _, _, call_stmt = body("""
def bump() -> int:
    return 2
def f(a: int, b: int = 7, c: int = 9) -> int:
    return a + b + c
result: int = f(c=bump(), a=1)
""")
    call = call_stmt.value
    assert isinstance(call, FunctionCall)
    assert call.omitted_arguments == (1,)
    assert call.argument_evaluation_order == (2, 0, 1)
    assert isinstance(call.supplied_evaluation_arguments[0], FunctionCall)
    assert call.supplied_evaluation_arguments[1] == Literal(1)
    assert call.arguments[1] == Literal(7)
    assert len(call.evaluation_arguments) == 3


def test_middle_keyword_default_omitted_and_last_supplied() -> None:
    definition, assign = body("""
def g(x: int, y: int = 3, z: int = 5) -> int:
    return x + y + z
result: int = g(1, z=9)
""")
    call = assign.value
    assert call.omitted_arguments == (1,)
    assert call.argument_evaluation_order == (0, 2, 1)
    assert call.arguments == (Literal(1), Literal(3), Literal(9))
    assert definition.signature.defaults_by_parameter[0] is None


def test_forward_reference_and_nested_default() -> None:
    top, f = body("""
def top() -> int:
    def inner(x: int = 4) -> int:
        return x
    return inner()
result: int = top()
""")
    nested_call = top.body.children[-1].value
    assert nested_call.omitted_arguments == (0,)
    assert nested_call.arguments == (Literal(4),)
    assert f.value.arguments == ()


def test_method_constructor_and_super_defaults() -> None:
    base, derived, create, invoke = body("""
class Base:
    def __init__(self, x: int = 4) -> None:
        self.x: int = x
    def get(self, shift: int = 2) -> int:
        return self.x + shift
class Derived(Base):
    def __init__(self, x: int = 6) -> None:
        super().__init__()
    def get(self, shift: int = 2) -> int:
        return super().get(shift=shift)
d: Derived = Derived()
result: int = d.get()
""")
    init_call = derived.methods[0].body.children[0].value
    super_call = derived.methods[1].body.children[0].value
    assert isinstance(init_call, MethodCall)
    assert init_call.omitted_arguments == (0,)
    assert init_call.arguments == (Literal(4),)
    assert isinstance(super_call, MethodCall)
    assert super_call.omitted_arguments == ()
    assert isinstance(create.value, InstanceCreation)
    assert create.value.omitted_arguments == (0,)
    assert create.value.arguments == (Literal(6),)
    assert invoke.value.omitted_arguments == (0,)
    assert invoke.value.arguments == (Literal(2),)
    assert base.methods[0].signature.parameter_defaults == (None, Literal(4))


def test_mixed_default_and_keyword_method() -> None:
    *_, result = body("""
class C:
    def __init__(self, x: int = 1) -> None:
        self.x: int = x
    def calc(self, a: int, b: int = 3, c: int = 4) -> int:
        return a + b + c
o: C = C()
x: int = o.calc(c=7, a=8)
""")
    call = result.value
    assert call.omitted_arguments == (1,)
    assert call.argument_evaluation_order == (2, 0, 1)
    assert call.arguments == (Literal(8), Literal(3), Literal(7))


def test_explicit_arguments_still_allowed() -> None:
    _, assign = body("""
def f(x: int = 1) -> int:
    return x
result: int = f(10)
""")
    assert assign.value.omitted_arguments == ()
    assert assign.value.supplied_evaluation_arguments == (Literal(10),)


@pytest.mark.parametrize(
    ("default", "annotation", "reason"),
    [
        ("[]", "list[int]", "scalar literal default"),
        ("{}", "dict[str, int]", "scalar literal default"),
        ("(1, 2)", "tuple[int, int]", "scalar literal default"),
        ("1 + 2", "int", "scalar literal default"),
        ("other", "int", "scalar literal default"),
        ("-True", "int", "scalar literal default"),
        ("float(1)", "float", "scalar literal default"),
        ('"text"', "int", "default argument type mismatch"),
        ("True", "int", "default argument type mismatch"),
        ("1", "float", "default argument type mismatch"),
        ("None", "int", "default argument type mismatch"),
        ("1e400", "float", "finite float"),
    ],
)
def test_reject_unsupported_defaults(
    default: str, annotation: str, reason: str
) -> None:
    with pytest.raises(UnsupportedPython, match=reason):
        body(f"def f(x: {annotation} = {default}) -> int:\n    return 1")


@pytest.mark.parametrize("expression", ["f()", "f(y=3)", "f(1, 2, 3)"])
def test_missing_required_or_too_many(expression: str) -> None:
    with pytest.raises(
        UnsupportedPython, match="(count mismatch|too many|Missing required)"
    ):
        body(
            """
def f(x: int, y: int = 2) -> int:
    return x + y
"""
            + f"value: int = {expression}"
        )


def test_default_in_function_value_does_not_imply_callable_omission() -> None:
    # CallableType has positional signature only, not a declaration default.
    with pytest.raises(UnsupportedPython, match="argument count mismatch"):
        body("""
from typing import Callable
def f(x: int = 2) -> int:
    return x
g: Callable[[int], int] = f
result: int = g()
""")


def test_model_rejects_wrong_default_shapes() -> None:
    param = Symbol("x", ValueType(ValueKind.INTEGER), "int")
    with pytest.raises(ConstructError, match="align"):
        FunctionSignature(
            "f",
            (param,),
            "int",
            ValueType(ValueKind.INTEGER),
            parameter_defaults=(None, Literal(2)),
        )
    with pytest.raises(ConstructError, match="type mismatch"):
        FunctionSignature(
            "f",
            (param,),
            "int",
            ValueType(ValueKind.INTEGER),
            parameter_defaults=(Literal("oops"),),
        )
    with pytest.raises(ConstructError, match="scalar"):
        FunctionSignature(
            "f",
            (param,),
            "int",
            ValueType(ValueKind.INTEGER),
            parameter_defaults=(
                FunctionCall(
                    FunctionSignature("g", (), "int", ValueType(ValueKind.INTEGER)), ()
                ),
            ),
        )


def test_model_rejects_invalid_omission_metadata() -> None:
    p = Symbol("x", ValueType(ValueKind.INTEGER), "int")
    sig = FunctionSignature(
        "f", (p,), "int", ValueType(ValueKind.INTEGER), parameter_defaults=(Literal(2),)
    )
    with pytest.raises(ConstructError, match="default"):
        FunctionCall(sig, (Literal(3),), (0,), (0,))
    with pytest.raises(ConstructError, match="sorted unique"):
        FunctionCall(sig, (Literal(2),), (0,), (0, 0))
    with pytest.raises(ConstructError, match="permutation"):
        FunctionCall(sig, (Literal(2),), (1,), (0,))


def test_overriding_defaults_must_be_the_same_for_virtual_dispatch() -> None:
    with pytest.raises(UnsupportedPython, match="preserve parameter defaults"):
        body("""
class A:
    def __init__(self) -> None:
        self.x: int = 1
    def get(self, n: int = 2) -> int:
        return n
class B(A):
    def __init__(self) -> None:
        super().__init__()
    def get(self, n: int = 3) -> int:
        return n
""")


def test_virtual_override_with_identical_defaults_is_safe() -> None:
    *_, result = body("""
class A:
    def __init__(self) -> None:
        self.x: int = 1
    def get(self, n: int = 2) -> int:
        return n
class B(A):
    def __init__(self) -> None:
        super().__init__()
    def get(self, n: int = 2) -> int:
        return n
v: A = B()
result: int = v.get()
""")
    assert result.value.omitted_arguments == (0,)
    assert result.value.arguments == (Literal(2),)
