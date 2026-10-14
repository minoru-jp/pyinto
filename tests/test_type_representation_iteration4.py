"""Iteration 4: a single declared function result type and typed annotations."""

from __future__ import annotations

import ast

import pytest

from pyinto.constructs import (
    CallableType,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    FunctionSignature,
    ListType,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.frontend import PythonFrontend
from pyinto.frontend.annotations import AnnotationScope, parse_annotation
from pyinto.interface_mapping import InterfaceMappingRegistry


def test_signature_return_type_is_the_single_structural_shape() -> None:
    result_type = ValueType(
        ValueKind.FUNCTION,
        callable_type=CallableType(
            (ValueType(ValueKind.INTEGER),),
            ValueType(ValueKind.LIST, list_type=ListType(ValueType(ValueKind.STRING))),
        ),
    )
    signature = FunctionSignature(
        "factory", (), "Callable[[int], list[str]]", result_type
    )
    assert signature.return_type is result_type
    assert signature.callable_type.return_type is result_type
    assert signature.value_symbol.callable_type == signature.callable_type
    assert FunctionCall(signature, ()).value_type == result_type
    assert not hasattr(signature, "return_kind")
    assert not hasattr(signature, "return_list_type")


def test_invalid_signature_result_type_is_rejected() -> None:
    with pytest.raises(ConstructError, match="return ValueType"):
        FunctionSignature("wrong", (), "int", ValueKind.INTEGER)  # type: ignore[arg-type]


def test_annotation_parser_returns_one_value_type_even_when_nested() -> None:
    scope = AnnotationScope({}, set(), {"Callable"}, {}, InterfaceMappingRegistry())
    expression = ast.parse("Callable[[list[int]], tuple[str, bool]]", mode="eval").body
    spelling, result = parse_annotation(expression, scope)
    assert spelling == "Callable[[list[int]], tuple[str, bool]]"
    assert result is not None
    assert result.callable_type is not None
    assert result.callable_type.parameter_types[0].list_type == ListType(
        ValueType(ValueKind.INTEGER)
    )
    assert result.callable_type.return_type.tuple_type is not None
    assert [
        t.kind for t in result.callable_type.return_type.tuple_type.element_types
    ] == [
        ValueKind.STRING,
        ValueKind.BOOLEAN,
    ]


def test_frontend_preserves_one_return_type_across_function_and_call() -> None:
    model = PythonFrontend().parse(
        """
from typing import Callable

def make(x: int) -> Callable[[int], int]:
    return lambda y: x + y

f: Callable[[int], int] = make(1)
"""
    )
    definition = model.body.children[0]
    assert isinstance(definition, FunctionDefinition)
    signature = definition.signature
    assert signature.return_type.callable_type is not None
    init = model.body.children[1]
    call = init.value  # type: ignore[attr-defined]
    assert isinstance(call, FunctionCall)
    assert call.value_type == signature.return_type
    assert isinstance(signature.parameters[0], Symbol)
