"""Iteration 44: limited Python global directives preserve typed module identity.

These are source-admission/Model tests. Target realization of shared module
storage remains an independent capability, not implied by normalization.
"""

# The AST fixtures intentionally concatenate adjacent source-code lines.
# ruff: noqa: ISC004
from __future__ import annotations

import pytest

from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    Arithmetic,
    Assign,
    FunctionCall,
    FunctionDefinition,
    Initialize,
    Reference,
    Return,
    ValueKind,
)
from pyinto.frontend import PythonFrontend, UnsupportedPython


def parse(source: str):
    return PythonFrontend().parse(source).body.children


def test_global_write_and_read_reuse_exact_module_symbol() -> None:
    original, definition, invocation, observed = parse(
        "counter: int = 0\n"
        "def increment() -> None:\n"
        "    global counter\n"
        "    counter = counter + 1\n"
        "increment()\n"
        "after: int = counter\n"
    )
    assert isinstance(original, Initialize)
    assert original.symbol.scope == ()
    assert isinstance(definition, FunctionDefinition)
    assert len(definition.body.children) == 1  # no Global/Pass Construct
    assignment = definition.body.children[0]
    assert isinstance(assignment, Assign)
    assert assignment.target.symbol is original.symbol
    assert isinstance(assignment.value, Arithmetic)
    assert isinstance(assignment.value.left, Reference)
    assert assignment.value.left.symbol is original.symbol
    assert isinstance(invocation.value, FunctionCall)
    assert invocation.value.signature is definition.signature
    assert observed.value.symbol is original.symbol
    assert lexical_captures(definition) == ()


def test_global_prefix_after_docstring_and_multiple_bindings() -> None:
    first, second, definition = parse(
        "x: int = 0\ny: str = 'old'\n"
        "def update() -> int:\n"
        '    """update both"""\n'
        "    global x, y\n"
        "    x = 2\n"
        "    y = 'new'\n"
        "    return x\n"
    )
    assert definition.docstring == "update both"
    first_write, second_write, result = definition.body.children
    assert isinstance(first_write, Assign)
    assert isinstance(second_write, Assign)
    assert first_write.target.symbol is first.symbol
    assert second_write.target.symbol is second.symbol
    assert isinstance(result, Return)
    assert isinstance(result.value, Reference)
    assert result.value.symbol is first.symbol


def test_global_directive_can_be_read_only() -> None:
    declaration, definition = parse(
        "counter: int = 17\n"
        "def read() -> int:\n"
        "    global counter\n"
        "    return counter\n"
    )
    assert definition.body.children[0].value.symbol is declaration.symbol


def test_global_assignment_inside_control_body_keeps_module_symbol() -> None:
    declaration, definition = parse(
        "counter: int = 0\n"
        "def update(flag: bool) -> None:\n"
        "    global counter\n"
        "    if flag:\n"
        "        counter = 7\n"
        "    else:\n"
        "        counter = 8\n"
    )
    branch = definition.body.children[0]
    for write in (
        branch.then_body.children[0],
        branch.else_body.children[0],
    ):
        assert isinstance(write, Assign)
        assert write.target.symbol is declaration.symbol


def test_module_name_still_not_writable_without_global() -> None:
    with pytest.raises(UnsupportedPython, match="type annotation"):
        parse("counter: int = 0\ndef write() -> None:\n    counter = 1\n")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "def update() -> None:\n    global counter\n    counter = 1\n"
            "counter: int = 0\n",
            "earlier typed module variable",
        ),
        (
            "def update() -> None:\n    global missing\n    missing = 1\n",
            "earlier typed module variable",
        ),
        (
            "counter: int = 0\ndef f(counter: int) -> None:\n"
            "    global counter\n    counter = 1\n",
            "function parameter",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n    global counter, counter\n",
            "Duplicate global",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n"
            "    global counter\n    global counter\n",
            "Duplicate global",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n    counter = 1\n    global counter\n",
            "leading function directive",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n"
            "    if True:\n        global counter\n"
            "    counter = 1\n",
            "leading function directive",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n"
            "    global counter\n    counter: int = 1\n",
            "cannot be redeclared",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n"
            "    global counter\n    counter = 'wrong'\n",
            "Variable type cannot change",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n"
            "    global counter\n    for counter in range(2):\n"
            "        pass\n",
            "global for-target",
        ),
        (
            "counter: int = 0\ndef outer() -> None:\n"
            "    def inner() -> None:\n"
            "        global counter\n        counter = 1\n",
            "top-level functions",
        ),
        (
            "counter: int = 0\nclass Counter:\n"
            "    def __init__(self) -> None:\n        pass\n"
            "    def update(self) -> None:\n"
            "        global counter\n        counter = 1\n",
            "top-level functions",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n"
            "    global counter\n"
            "    def counter() -> int:\n"
            "        return 1\n",
            "nested function name",
        ),
        (
            "counter: int = 0\nglobal counter\n",
            "Unsupported statement",
        ),
        (
            "counter: int = 0\ndef f() -> None:\n    nonlocal counter\n",
            "Unsupported statement",
        ),
    ],
)
def test_reject_outside_explicit_global_subset(source: str, message: str) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        parse(source)


def test_nested_function_reads_ordinary_module_value_unchanged() -> None:
    declaration, outer = parse(
        "counter: int = 1\n"
        "def outer() -> int:\n"
        "    def inner() -> int:\n"
        "        return counter\n"
        "    return inner()\n"
    )
    inner = outer.body.children[0]
    assert inner.body.children[0].value.symbol is declaration.symbol
    assert lexical_captures(inner) == ()


def test_globals_do_not_leak_into_another_function() -> None:
    with pytest.raises(UnsupportedPython, match="type annotation"):
        parse(
            "counter: int = 0\n"
            "def write() -> None:\n"
            "    global counter\n    counter = 1\n"
            "def unsafe() -> None:\n"
            "    counter = 2\n"
        )


def test_failed_parse_restores_globals_and_new_parse_is_clean() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython, match="cannot be redeclared"):
        frontend.parse(
            "counter: int = 0\n"
            "def write() -> None:\n"
            "    global counter\n    counter: int = 1\n"
        )
    assert frontend._context.names.global_names == set()
    assert frontend._context.names.enclosing_scopes == []
    assert frontend._context.names.active_function is None
    new = frontend.parse("a: int = 1\ndef f() -> int:\n    return a\n")
    assert new.body.children[-1].body.children[0].value.kind is ValueKind.INTEGER
    assert frontend._context.names.global_names == set()


def test_c_target_does_not_claim_unsupported_shared_state_realization() -> None:
    from pyinto import ConstructError, realize
    from tests.support.c_realizer import c_bindings

    program = PythonFrontend().parse(
        "counter: int = 0\n"
        "def update() -> None:\n"
        "    global counter\n"
        "    counter = counter + 1\n"
    )
    with pytest.raises(ConstructError):
        realize(program, realizations=c_bindings())
