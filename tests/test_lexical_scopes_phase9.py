"""SDD phase 9: scoped names and nested functions, using existing Constructs."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Arithmetic,
    ConstructError,
    FunctionCall,
    FunctionDefinition,
    Initialize,
    Reference,
    Return,
    ValueKind,
)
from tests.support.c_realizer import c_bindings


def _contains_python_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, tuple):
        return any(_contains_python_ast(part) for part in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(
            _contains_python_ast(getattr(value, part.name)) for part in fields(value)
        )
    return False


def test_frt_011_immediate_nested_definition_and_outer_parameter_capture() -> None:
    program = PythonFrontend().parse(
        "def outer(x: int) -> int:\n"
        "    def inner(y: int) -> int:\n"
        "        return x + y\n"
        "    return inner(3)\n"
    )
    outer = program.body.children[0]
    assert isinstance(outer, FunctionDefinition)
    inner, exit_outer = outer.body.children
    assert isinstance(inner, FunctionDefinition)
    assert isinstance(exit_outer, Return)
    assert inner.signature.scope == ("outer",)
    assert inner.signature.parameters[0].scope == ("outer", "inner")
    assert outer.signature.scope == ()
    assert outer.signature.parameters[0].scope == ("outer",)
    inner_return = inner.body.children[0]
    assert isinstance(inner_return, Return)
    assert isinstance(inner_return.value, Arithmetic)
    left, right = inner_return.value.left, inner_return.value.right
    assert isinstance(left, Reference) and isinstance(right, Reference)
    assert left.symbol is outer.signature.parameters[0]
    assert right.symbol is inner.signature.parameters[0]
    assert isinstance(exit_outer.value, FunctionCall)
    assert exit_outer.value.signature is inner.signature
    assert not _contains_python_ast(program)


def test_frt_011_arbitrary_lexical_depth_retains_correct_declaration() -> None:
    source = (
        "def level0(a: int) -> int:\n"
        "    def level1(b: int) -> int:\n"
        "        def level2(c: int) -> int:\n"
        "            def level3(d: int) -> int:\n"
        "                return a + b + c + d\n"
        "            return level3(4)\n"
        "        return level2(3)\n"
        "    return level1(2)\n"
    )
    root = PythonFrontend().parse(source).body.children[0]
    assert isinstance(root, FunctionDefinition)
    one = root.body.children[0]
    two = one.body.children[0]
    three = two.body.children[0]
    assert all(isinstance(f, FunctionDefinition) for f in (one, two, three))
    assert three.signature.scope == ("level0", "level1", "level2")
    assert one.body.children[1].value.signature is two.signature
    assert two.body.children[1].value.signature is three.signature
    assert root.body.children[1].value.signature is one.signature
    expr = three.body.children[0].value
    # Flatten only for assertions; the Construct tree itself stays nested.
    references = [expr.right]
    left = expr.left
    while isinstance(left, Arithmetic):
        references.append(left.right)
        left = left.left
    references.append(left)
    assert [ref.symbol for ref in reversed(references)] == [
        root.signature.parameters[0],
        one.signature.parameters[0],
        two.signature.parameters[0],
        three.signature.parameters[0],
    ]
    assert [ref.symbol.scope for ref in reversed(references)] == [
        ("level0",),
        ("level0", "level1"),
        ("level0", "level1", "level2"),
        ("level0", "level1", "level2", "level3"),
    ]


def test_frt_011_nested_siblings_forward_calls_and_recursion() -> None:
    root = (
        PythonFrontend()
        .parse(
            "def outer(n: int) -> int:\n"
            "    def first(x: int) -> int:\n"
            "        return second(x)\n"
            "    def second(y: int) -> int:\n"
            "        if y == 0:\n"
            "            return 0\n"
            "        return first(y - 1)\n"
            "    return first(n)\n"
        )
        .body.children[0]
    )
    first, second, ret = root.body.children
    assert first.body.children[0].value.signature is second.signature
    assert second.body.children[1].value.signature is first.signature
    assert ret.value.signature is first.signature


def test_frt_011_shadowing_function_names_uses_nearest_scope() -> None:
    root, other = (
        PythonFrontend()
        .parse(
            "def outer() -> int:\n"
            "    def helper() -> int:\n"
            "        return 1\n"
            "    def nested() -> int:\n"
            "        def helper() -> int:\n"
            "            return 2\n"
            "        return helper()\n"
            "    return nested()\n"
            "def other() -> int:\n"
            "    def helper() -> int:\n"
            "        return 3\n"
            "    return helper()\n"
        )
        .body.children
    )
    outer_helper, nested, exit_outer = root.body.children
    inner_helper, exit_nested = nested.body.children
    other_helper, exit_other = other.body.children
    assert outer_helper.signature != inner_helper.signature
    assert outer_helper.signature != other_helper.signature
    assert inner_helper.signature != other_helper.signature
    assert inner_helper.signature.scope == ("outer", "nested")
    assert outer_helper.signature.scope == ("outer",)
    assert other_helper.signature.scope == ("other",)
    assert exit_nested.value.signature is inner_helper.signature
    assert exit_other.value.signature is other_helper.signature
    assert exit_outer.value.signature is nested.signature


def test_frt_011_parameter_shadow_and_local_capture_by_identity() -> None:
    root = PythonFrontend().parse(
        "value: int = 99\n"
        "def outer(value: int) -> int:\n"
        "    local: int = value\n"
        "    def inner(value: int) -> int:\n"
        "        return local + value\n"
        "    return inner(4)\n"
    )
    module_value, outer = root.body.children
    local_decl, inner, exit_outer = outer.body.children
    assert isinstance(module_value, Initialize)
    assert isinstance(local_decl, Initialize)
    expr = inner.body.children[0].value
    assert expr.left.symbol is local_decl.symbol
    assert expr.right.symbol is inner.signature.parameters[0]
    assert expr.right.symbol != outer.signature.parameters[0]
    assert expr.right.symbol != module_value.symbol
    assert local_decl.symbol.scope == ("outer",)
    assert exit_outer.value.signature is inner.signature


def test_frt_011_inner_locals_do_not_escape_and_parent_is_not_contaminated() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        frontend.parse(
            "def outer() -> int:\n"
            "    def inner() -> int:\n"
            "        secret: int = 3\n"
            "        return secret\n"
            "    return secret\n"
        )
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        frontend.parse(
            "def outer() -> int:\n"
            "    def inner() -> int:\n"
            "        return 1\n"
            "    return inner()\n"
            "v: int = inner()\n"
        )


def test_frt_011_read_before_local_declaration_not_resolved_to_outer() -> None:
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        PythonFrontend().parse(
            "def outer(x: int) -> int:\n"
            "    def inner() -> int:\n"
            "        return x\n"
            "        x: int = 5\n"
            "    return inner()\n"
        )
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        PythonFrontend().parse(
            "x: int = 8\n"
            "def outer() -> int:\n"
            "    def inner() -> int:\n"
            "        return x\n"
            "    x: int = 5\n"
            "    return inner()\n"
        )


def test_frt_011_nested_function_name_conflicting_with_parameter_rejected() -> None:
    with pytest.raises(UnsupportedPython, match="conflicts with a parameter"):
        PythonFrontend().parse(
            "def outer(inner: int) -> int:\n"
            "    def inner() -> int:\n"
            "        return 1\n"
            "    return 0\n"
        )


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (
            (
                "def outer() -> int:\n"
                "    if 1 < 2:\n"
                "        def inner() -> int:\n"
                "            return 1\n"
                "    return 1\n"
            ),
            "control-flow blocks",
        ),
        (
            (
                "def outer() -> int:\n"
                "    while 1 < 2:\n"
                "        def inner() -> int:\n"
                "            return 1\n"
                "    return 1\n"
            ),
            "control-flow blocks",
        ),
        (
            (
                "def outer() -> int:\n"
                "    x: int = 1\n"
                "    def inner() -> int:\n"
                "        nonlocal x\n"
                "        x = 2\n"
                "        return x\n"
                "    return inner()\n"
            ),
            "Unsupported statement",
        ),
        (
            (
                "def outer() -> int:\n"
                "    def inner() -> int:\n"
                "        return 1\n"
                "    return inner\n"
            ),
            "Return type mismatch",
        ),
        (
            (
                "def outer() -> int:\n"
                "    def inner() -> int:\n"
                "        return 1\n"
                "    return inner()\n"
                "def outside() -> int:\n"
                "    return inner()\n"
            ),
            "Unregistered interface mapping call",
        ),
        (
            (
                "def outer() -> int:\n"
                "    def inner(x: int) -> int:\n"
                "        return x\n"
                "    return inner('bad')\n"
            ),
            "argument type mismatch",
        ),
    ],
)
def test_frt_012_unsupported_lexical_mechanisms_rejected(
    source: str, reason: str
) -> None:
    with pytest.raises(UnsupportedPython, match=reason):
        PythonFrontend().parse(source)


def test_frt_011_nested_realization_not_inferred() -> None:
    model = PythonFrontend().parse(
        "def outer(x: int) -> int:\n"
        "    def inner(y: int) -> int:\n"
        "        return x + y\n"
        "    return inner(4)\n"
    )
    before = repr(model)
    with pytest.raises(
        ConstructError, match="No 'c' realization for FunctionDefinition"
    ):
        realize(model, realizations=c_bindings())
    assert repr(model) == before


def test_frt_011_frontend_instance_does_not_leak_nested_bindings() -> None:
    frontend = PythonFrontend()
    model = frontend.parse(
        "def outer() -> int:\n"
        "    def inner() -> int:\n"
        "        return 1\n"
        "    return inner()\n"
    )
    assert frontend.parse("def outer() -> int:\n    return 2\n") != model
    with pytest.raises(UnsupportedPython, match="Unregistered interface mapping call"):
        frontend.parse("answer: int = inner()")


def test_frt_011_named_function_call_keeps_return_kind() -> None:
    root = (
        PythonFrontend()
        .parse(
            "def outer() -> None:\n"
            "    def inner() -> None:\n"
            "        return\n"
            "    inner()\n"
            "    return\n"
        )
        .body.children[0]
    )
    assert isinstance(root.body.children[1].value, FunctionCall)
    assert root.body.children[1].value.kind is ValueKind.NONE
