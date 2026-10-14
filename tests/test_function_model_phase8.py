"""SDD phase 8: typed function signatures, returns and scoped calls (Model only)."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Arithmetic,
    Assign,
    Block,
    Comparison,
    ConstructError,
    ExpressionStatement,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    Initialize,
    Literal,
    Parameter,
    Reference,
    Return,
    Symbol,
    ValueKind,
    ValueType,
)
from tests.support.c_realizer import c_bindings


def _has_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, tuple):
        return any(_has_ast(child) for child in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_has_ast(getattr(value, f.name)) for f in fields(value))
    return False


def test_cst_017_signature_and_parameter_contract() -> None:
    param = Symbol("number", ValueType(ValueKind.INTEGER), "int")
    signature = FunctionSignature(
        "identity", (param,), "int", ValueType(ValueKind.INTEGER)
    )
    definition = FunctionDefinition(signature, Block((Return(Reference(param)),)))
    assert definition.signature == signature
    assert definition.parts()["name"].value == "identity"
    assert definition.parts()["parameters"] == (Parameter(param),)
    assert definition.parts()["body"] == definition.body
    assert Parameter(param).parts()["type"] is param
    assert Parameter(param).parts()["name"].value == "number"
    assert definition.variant() == "default"


def test_cst_018_call_arguments_and_return_are_structural() -> None:
    symbol = Symbol("n", ValueType(ValueKind.INTEGER), "int")
    signature = FunctionSignature(
        "square", (symbol,), "int", ValueType(ValueKind.INTEGER)
    )
    call = FunctionCall(signature, (Literal(5),))
    assert call.kind is ValueKind.INTEGER
    assert call.parts() == {"callee": call.parts()["callee"], "arg0": Literal(5)}
    assert call.parts()["callee"].value == "square"
    assert FunctionCall.accepts_part_name("arg0")
    assert not FunctionCall.accepts_part_name("arg01")
    assert Return().parts() == {}
    assert Return().variant() == "default"
    assert Return(call).parts()["value"] is call
    assert Return(call).variant() == "with_value"


def test_cst_017_018_bad_model_fails_at_construction() -> None:
    symbol = Symbol("n", ValueType(ValueKind.INTEGER), "int")
    signature = FunctionSignature("f", (symbol,), "int", ValueType(ValueKind.INTEGER))
    for args, message in [
        ((), "count mismatch"),
        ((Literal("oops"),), "type mismatch"),
    ]:
        with pytest.raises(ConstructError, match=message):
            FunctionCall(signature, args)
    with pytest.raises(ConstructError, match="Duplicate function parameter"):
        FunctionSignature("f", (symbol, symbol), "int", ValueType(ValueKind.INTEGER))
    with pytest.raises(ConstructError, match="identifier"):
        FunctionSignature("not-a-name", (), "int", ValueType(ValueKind.INTEGER))


def test_frt_009_local_scope_and_typed_result() -> None:
    program = PythonFrontend().parse(
        "global_count: int = 4\n"
        "def calculate(n: int) -> int:\n"
        "    step: int = global_count + n\n"
        "    if step > 5:\n"
        "        return step\n"
        "    return n\n"
        "result: int = calculate(global_count)\n"
    )
    global_decl, definition, result = program.body.children
    assert isinstance(global_decl, Initialize)
    assert isinstance(definition, FunctionDefinition)
    assert isinstance(result, Initialize)
    assert isinstance(result.value, FunctionCall)
    assert definition.signature == result.value.signature
    assert definition.signature.return_annotation == "int"
    assert isinstance(definition.body.children[0], Initialize)
    assert isinstance(definition.body.children[0].value, Arithmetic)
    assert isinstance(definition.body.children[0].value.left, Reference)
    assert definition.body.children[0].value.left.symbol.name == "global_count"
    branch, final_return = definition.body.children[1:]
    assert isinstance(branch.condition, Comparison)
    assert isinstance(branch.then_body.children[0], Return)
    assert isinstance(final_return, Return)
    assert final_return.value == Reference(definition.signature.parameters[0])
    assert not _has_ast(program)


def test_frt_010_forward_and_recursive_function_refs() -> None:
    program = PythonFrontend().parse(
        "def outer(n: int) -> int:\n"
        "    return inner(n)\n"
        "def inner(x: int) -> int:\n"
        "    if x == 0:\n"
        "        return 0\n"
        "    return outer(x - 1)\n"
    )
    outer, inner = program.body.children
    assert isinstance(outer, FunctionDefinition)
    assert isinstance(inner, FunctionDefinition)
    call = outer.body.children[0].value
    assert isinstance(call, FunctionCall)
    assert call.signature == inner.signature
    recursion = inner.body.children[1].value
    assert isinstance(recursion, FunctionCall)
    assert recursion.signature == outer.signature


def test_frt_009_none_return_with_void_function_call() -> None:
    program = PythonFrontend().parse(
        "def notify() -> None:\n    return None\nnotify()\n"
    )
    definition, invoke = program.body.children
    assert definition.signature.return_type.kind is ValueKind.NONE
    assert definition.body.children == (Return(),)
    assert isinstance(invoke, ExpressionStatement)
    assert isinstance(invoke.value, FunctionCall)
    assert invoke.value.kind is ValueKind.NONE


def test_frt_009_parameters_are_not_global_bindings() -> None:
    program = PythonFrontend().parse(
        "x: int = 4\n"
        "def first(x: int) -> int:\n"
        "    return x\n"
        "def second(x: int) -> int:\n"
        "    local: int = x\n"
        "    return local\n"
        "x = 5\n"
    )
    global_symbol = program.body.children[0].symbol
    first, second = program.body.children[1:3]
    param1, param2 = first.signature.parameters[0], second.signature.parameters[0]
    assert first.body.children[0].value.symbol is param1
    assert second.body.children[0].value.symbol is param2
    assert param1 is not global_symbol and param2 is not global_symbol
    assert isinstance(program.body.children[-1], Assign)
    assert program.body.children[-1].target.symbol is global_symbol


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        ("def f(x) -> int:\n    return 1", "parameter needs annotation"),
        ("def f(x: int):\n    return x", "requires simple typed"),
        ("def f(x: int = []) -> int:\n    return x", "scalar literal default"),
        ("def f(*args) -> int:\n    return 1", "Variadic parameter needs"),
        ("def f(*, k: int) -> int:\n    return k", "requires simple typed"),
        (
            "def f(x: int) -> int:\n    return x\ndef f(y: int) -> int:\n    return y",
            "Duplicate",
        ),
        ("def f(x: int, x: int) -> int:\n    return 1", "Duplicate"),
        ("return 5", "return requires a function"),
        ("def f() -> int:\n    return", "Return value is required"),
        ("def f() -> int:\n    return 'wrong'", "Return type mismatch"),
        ("def f() -> None:\n    return 1", "cannot return a value"),
        ("def f() -> int:\n    return 1\nx: int = f(1)", "argument count mismatch"),
        (
            "def f(x: int) -> int:\n    return x\nx: int = f('bad')",
            "argument type mismatch",
        ),
        (
            "def f(x: int) -> int:\n    return x\nx: int = f(y=2)",
            "Unknown keyword argument",
        ),
        ("def f() -> int:\n    return missing", "Unresolved name"),
        (
            "def f() -> int:\n    x: int = 2\n    return x\ny: int = x",
            "Unresolved name",
        ),
        ("def f() -> int:\n    return x\nx: int = 3", "Unresolved name"),
        (
            "x: int = 1\ndef f() -> int:\n    return x\n    x: int = 2",
            "Unresolved name",
        ),
        (
            "def f() -> int:\n    break\n    return 1",
            "break requires an enclosing loop",
        ),
        (
            "def f() -> int:\n    return 1\n@f\ndef g() -> int:\n    return 2",
            "requires simple typed",
        ),
        ("async def f() -> int:\n    return 1", "Async functions are unsupported"),
    ],
)
def test_frt_009_010_explicit_rejection(source: str, problem: str) -> None:
    with pytest.raises(UnsupportedPython, match=problem) as exc:
        PythonFrontend().parse(source)
    assert "line " in str(exc.value)


def test_sdd8_target_realization_remains_separate_and_model_is_reusable() -> None:
    source = "def double(n: int) -> int:\n    return n + n\n"
    model = PythonFrontend().parse(source)
    previous = repr(model)
    with pytest.raises(
        ConstructError, match="No 'c' realization for FunctionDefinition"
    ):
        realize(model, realizations=c_bindings())
    assert repr(model) == previous
    assert PythonFrontend().parse(source) == model


def test_frt_009_010_parser_resets_function_state_between_requests() -> None:
    frontend = PythonFrontend()
    frontend.parse("def x() -> int:\n    return 1")
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        frontend.parse("v: int = x()")


def test_frt_009_nested_definitions_in_if_or_loop_are_explicitly_rejected() -> None:
    for source in (
        "if 1 < 2:\n    def f() -> int:\n        return 1",
        "while 1 < 2:\n    def f() -> int:\n        return 1",
    ):
        with pytest.raises(UnsupportedPython, match="control-flow blocks"):
            PythonFrontend().parse(source)


def test_cst_018_return_rejects_non_value() -> None:
    with pytest.raises(ConstructError, match="requires a Value"):
        Return("bad")  # type: ignore[arg-type]
