"""Iteration 22: regression probes for normalization vs Target realization.

These assertions do not claim that the corresponding Target Realizations exist.
They capture the current Model contracts before any deliberate redesign.
"""

from __future__ import annotations

import pytest

from pyinto.constructs import (
    FunctionCall,
    FunctionDefinition,
    LambdaValue,
    Literal,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def test_dataclass_matches_explicit_typed_initialization_model() -> None:
    """Synthetically generated Python AST is an internal frontend detail."""
    generated = PythonFrontend().parse(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Item:\n"
        "    x: int\n"
        "    y: int = 3\n"
        "value: Item = Item(5)\n"
    )
    explicit = PythonFrontend().parse(
        "class Item:\n"
        "    def __init__(self, x: int, y: int = 3) -> None:\n"
        "        self.x: int = x\n"
        "        self.y: int = y\n"
        "value: Item = Item(5)\n"
    )
    assert generated == explicit


def test_argument_binding_order_is_not_expression_evaluation_order() -> None:
    tree = PythonFrontend().parse(
        "def a() -> int:\n    return 1\n"
        "def b() -> int:\n    return 2\n"
        "def f(x: int, y: int = 3, z: int = 4) -> int:\n"
        "    return x + y + z\n"
        "result: int = f(z=b(), x=a())\n"
    )
    call = tree.body.children[-1].value
    assert isinstance(call, FunctionCall)
    assert call.omitted_arguments == (1,)
    assert call.argument_evaluation_order == (2, 0, 1)
    assert tuple(arg.signature.name for arg in call.supplied_evaluation_arguments) == (
        "b",
        "a",
    )
    assert call.arguments[1] == Literal(3)
    # A default supplied by the declaration does not become a source expression.
    assert len(call.supplied_evaluation_arguments) == 2


def test_explicit_default_and_omitted_default_are_structurally_distinct() -> None:
    tree = PythonFrontend().parse(
        "def f(x: int = 3) -> int:\n    return x\n"
        "omitted: int = f()\n"
        "supplied: int = f(3)\n"
    )
    omitted = tree.body.children[1].value
    supplied = tree.body.children[2].value
    assert isinstance(omitted, FunctionCall)
    assert isinstance(supplied, FunctionCall)
    assert omitted.arguments == supplied.arguments
    assert omitted.omitted_arguments == (0,)
    assert supplied.omitted_arguments == ()
    assert omitted.supplied_evaluation_arguments == ()
    assert supplied.supplied_evaluation_arguments == (Literal(3),)


def test_lambda_internal_name_is_lexical_identity_not_python_binding() -> None:
    frontend = PythonFrontend()
    model = frontend.parse(
        "from typing import Callable\n"
        "__henkan_lambda_1: int = 2\n"
        "f: Callable[[int], int] = lambda x: x + __henkan_lambda_1\n"
    )
    lam = model.body.children[-1].value
    assert isinstance(lam, LambdaValue)
    assert isinstance(lam.definition, FunctionDefinition)
    assert lam.definition.signature.name != "__henkan_lambda_1"
    assert lam.definition.signature.name.startswith("__henkan_lambda_")
    assert "__henkan_lambda_1" not in frontend._context.names.functions
    assert frontend._context.flow.lambda_counter == 2


@pytest.mark.parametrize(
    "source",
    [
        "def f(x: list[int] = []) -> int:\n    return 1\n",
        (
            "def decorate(f: object) -> object:\n    return f\n"
            "@decorate\ndef f() -> int:\n    return 1\n"
        ),
    ],
)
def test_unadopted_dynamic_semantics_are_not_inferred(source: str) -> None:
    with pytest.raises(UnsupportedPython):
        PythonFrontend().parse(source)
