"""SDD phase 10: explicitly typed first-class function *values*, not indirect calls."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Assign,
    CallableType,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    Initialize,
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
    if isinstance(value, (tuple, list)):
        return any(_has_ast(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_has_ast(getattr(value, f.name)) for f in fields(value))
    return False


def test_cst_020_callable_type_is_recursive_structural_data() -> None:
    integer = ValueType(ValueKind.INTEGER)
    unit = ValueType(ValueKind.NONE)
    inner = CallableType((integer,), integer)
    outer = CallableType((ValueType(ValueKind.FUNCTION, inner),), unit)
    assert outer.annotation() == "Callable[[Callable[[int], int]], None]"
    assert outer == CallableType((ValueType(ValueKind.FUNCTION, inner),), unit)
    assert outer != CallableType((integer,), unit)
    assert not _has_ast(outer)
    with pytest.raises(ConstructError, match="callable shape"):
        ValueType(ValueKind.FUNCTION)
    with pytest.raises(ConstructError, match="callable shape"):
        ValueType(ValueKind.INTEGER, inner)
    with pytest.raises(ConstructError, match="Callable parameters"):
        CallableType((unit,), integer)
    with pytest.raises(ConstructError, match="mapped"):
        ValueType(ValueKind.MAPPED_OBJECT)
    with pytest.raises(ConstructError, match="Callable return"):
        CallableType((), "bad")  # type: ignore[arg-type]


def test_cst_020_function_symbol_validation_and_initializer_type() -> None:
    shape = CallableType((ValueType(ValueKind.INTEGER),), ValueType(ValueKind.STRING))
    with pytest.raises(ValueError, match="callable shape"):
        Symbol("f", ValueType(ValueKind.FUNCTION), "Callable[[int], str]")
    with pytest.raises(ValueError, match="callable shape"):
        Symbol("x", ValueType(ValueKind.INTEGER, callable_type=shape), "int")
    func = Symbol(
        "f", ValueType(ValueKind.FUNCTION, callable_type=shape), "Callable[[int], str]"
    )
    same = Symbol(
        "g", ValueType(ValueKind.FUNCTION, callable_type=shape), "Callable[[int], str]"
    )
    mismatched = Symbol(
        "h",
        ValueType(
            ValueKind.FUNCTION,
            callable_type=CallableType(
                (ValueType(ValueKind.STRING),), ValueType(ValueKind.STRING)
            ),
        ),
        "Callable[[str], str]",
    )
    assert Initialize(func, Reference(same)).value.kind is ValueKind.FUNCTION
    assert Assign(Reference(func), Reference(same)).value.callable_type == shape
    with pytest.raises(ConstructError, match="type mismatch"):
        Initialize(func, Reference(mismatched))
    with pytest.raises(ConstructError, match="type mismatch"):
        Assign(Reference(func), Reference(mismatched))


def test_cst_021_stable_function_declaration_symbol_and_reference() -> None:
    parameter = Symbol("x", ValueType(ValueKind.INTEGER), "int")
    signature = FunctionSignature(
        "inc", (parameter,), "int", ValueType(ValueKind.INTEGER)
    )
    assert signature.value_symbol is signature.value_symbol
    assert signature.value_symbol.kind is ValueKind.FUNCTION
    assert signature.value_symbol.scope == ()
    assert signature.value_symbol.callable_type == signature.callable_type
    assert Reference(signature.value_symbol).callable_type == signature.callable_type
    assert Reference(signature.value_symbol).parts()["name"].value == "inc"
    assert signature.callable_type.annotation() == "Callable[[int], int]"
    with pytest.raises(ConstructError, match="callable shape"):
        FunctionSignature("incorrect", (), "int", ValueType(ValueKind.FUNCTION))


def test_frt_013_function_value_assignment_and_declaration_reference() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def inc(n: int) -> int:\n"
        "    return n + 1\n"
        "a: Callable[[int], int] = inc\n"
        "b: Callable[[int], int] = a\n"
        "a = inc\n"
    )
    definition, declaration, alias, assign = program.body.children
    assert isinstance(definition, FunctionDefinition)
    assert isinstance(declaration, Initialize)
    assert isinstance(alias, Initialize)
    assert isinstance(assign, Assign)
    assert declaration.symbol.callable_type == definition.signature.callable_type
    assert isinstance(declaration.value, Reference)
    assert declaration.value.symbol is definition.signature.value_symbol
    assert alias.value.symbol is declaration.symbol
    assert assign.value.symbol is definition.signature.value_symbol
    assert assign.target.symbol is declaration.symbol
    assert not _has_ast(program)


def test_frt_013_callable_parameter_and_function_argument() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable as Fn\n"
        "def inc(n: int) -> int:\n"
        "    return n + 1\n"
        "def accept(fn: Fn[[int], int]) -> Fn[[int], int]:\n"
        "    return fn\n"
        "received: Fn[[int], int] = accept(inc)\n"
    )
    inc, accept, received = program.body.children
    fn = accept.signature.parameters[0]
    assert fn.kind is ValueKind.FUNCTION
    assert fn.callable_type == inc.signature.callable_type
    returned = accept.body.children[0]
    assert isinstance(returned, Return)
    assert isinstance(returned.value, Reference)
    assert returned.value.symbol is fn
    call = received.value
    assert isinstance(call, FunctionCall)
    assert call.arguments[0].symbol is inc.signature.value_symbol
    assert call.kind is ValueKind.FUNCTION
    assert call.callable_type == inc.signature.callable_type


def test_frt_013_lexical_function_capture_and_escape_model() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def make(x: int) -> Callable[[], int]:\n"
        "    def get() -> int:\n"
        "        return x\n"
        "    return get\n"
        "first: Callable[[], int] = make(1)\n"
        "second: Callable[[], int] = make(2)\n"
    )
    make, first, second = program.body.children
    nested, returned = make.body.children
    assert isinstance(nested, FunctionDefinition)
    assert nested.signature.scope == ("make",)
    assert nested.signature.value_symbol.scope == ("make",)
    assert returned.value.symbol is nested.signature.value_symbol
    captured = nested.body.children[0].value
    assert captured.symbol is make.signature.parameters[0]
    assert first.value.signature is make.signature
    assert second.value.signature is make.signature
    assert first.value.callable_type == nested.signature.callable_type
    assert second.value.callable_type == nested.signature.callable_type
    assert first.symbol.callable_type == second.symbol.callable_type
    assert not _has_ast(program)


def test_frt_013_nested_callable_types_and_forward_declaration() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def factory() -> Callable[[Callable[[int], int]], int]:\n"
        "    return process\n"
        "def process(f: Callable[[int], int]) -> int:\n"
        "    return 7\n"
    )
    factory, process = program.body.children
    returned = factory.body.children[0]
    assert returned.value.symbol is process.signature.value_symbol
    assert (
        factory.signature.return_type.callable_type == process.signature.callable_type
    )
    assert process.signature.parameters[0].callable_type is not None


def test_frt_013_annotations_reset_across_parses() -> None:
    frontend = PythonFrontend()
    frontend.parse("from typing import Callable\n")
    with pytest.raises(UnsupportedPython, match="imported Callable"):
        frontend.parse("f: Callable[[int], int] = 1\n")


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (
            (
                "from typing import Callable\n"
                + "def f(x: int) -> int:\n    return x\n"
                + "g: Callable[[str], int] = f\n"
            ),
            "Annotated type does not match initializer",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f(x: int) -> int:\n    return x\n"
                + "g: Callable[[int], int] = f\n"
                + "g = 2\n"
            ),
            "Variable type cannot change",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f() -> Callable[[int], int]:\n"
                + "    def g(x: str) -> int:\n        return 2\n"
                + "    return g\n"
            ),
            "Return type mismatch",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f(x: int) -> int:\n    return x\n"
                + "def take(g: Callable[[str], int]) -> int:\n    return 1\n"
                + "take(f)\n"
            ),
            "Function argument type mismatch",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f() -> Callable[..., int]:\n    return 1\n"
            ),
            "explicit parameter list",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f() -> Callable[[int], float]:\n    return 1\n"
            ),
            "Return type mismatch",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f(x: Callable[[None], int]) -> int:\n    return 1\n"
            ),
            "Unsupported Callable parameter",
        ),
        (
            "from typing import Callable\ndef f(x: None) -> int:\n    return 1\n",
            "None is not a parameter type",
        ),
        (
            "from typing import Callable\nf: Callable[[int], int] = unknown\n",
            "Unresolved name",
        ),
        (
            (
                "from typing import Callable\n"
                + "def f(x: int) -> int:\n    return x\n"
                + "f: Callable[[int], int] = f\n"
            ),
            "Cannot shadow",
        ),
    ],
)
def test_frt_014_explicit_boundaries(source: str, reason: str) -> None:
    with pytest.raises(UnsupportedPython, match=reason):
        PythonFrontend().parse(source)


def test_frt_014_first_class_function_without_realization_fails_explicitly() -> None:
    program = PythonFrontend().parse(
        "from typing import Callable\n"
        "def f(n: int) -> int:\n    return n\n"
        "g: Callable[[int], int] = f\n"
    )
    with pytest.raises(ConstructError, match="[Uu]nregistered|[Mm]issing|[Nn]o "):
        realize(program, realizations=c_bindings())
