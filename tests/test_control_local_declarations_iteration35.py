"""Iteration 35: block-contained typed initializers, without new Python scopes."""

from __future__ import annotations

import pytest

from pyinto import PythonFrontend, UnsupportedPython
from pyinto.constructs import (
    Assign,
    Branch,
    For,
    FunctionDefinition,
    Initialize,
    Reference,
    While,
    With,
)


def test_if_local_declaration_and_following_same_block_reads_identity() -> None:
    program = PythonFrontend().parse("""
flag: bool = True
if flag:
    value: int = 4
    value = value + 1
    print(value)
""")
    branch = program.body.children[1]
    assert isinstance(branch, Branch)
    init, assignment, _ = branch.then_body.children
    assert isinstance(init, Initialize)
    assert isinstance(assignment, Assign)
    assert assignment.target.symbol is init.symbol
    assert isinstance(assignment.value.left, Reference)  # type: ignore[attr-defined]
    assert assignment.value.left.symbol is init.symbol  # type: ignore[attr-defined]
    assert init.symbol.scope == ()  # No synthetic Python block scope.


def test_if_else_each_has_private_declarations() -> None:
    program = PythonFrontend().parse("""
flag: bool = True
if flag:
    item: int = 1
    print(item)
else:
    item: str = 'different'
    print(item)
""")
    branch = program.body.children[1]
    assert isinstance(branch, Branch)
    assert branch.else_body is not None
    assert branch.then_body.children[0].symbol.kind.value == "integer"  # type: ignore[attr-defined]
    assert branch.else_body.children[0].symbol.kind.value == "string"  # type: ignore[attr-defined]


def test_control_declaration_nested_and_no_promotion_into_enclosing_block() -> None:
    program = PythonFrontend().parse("""
flag: bool = True
if flag:
    outer: int = 3
    while outer > 0:
        inner: int = outer
        print(inner)
        outer = outer - 1
    print(outer)
""")
    branch = program.body.children[1]
    assert isinstance(branch, Branch)
    loop = branch.then_body.children[1]
    assert isinstance(loop, While)
    assert isinstance(loop.body.children[0], Initialize)
    outer = branch.then_body.children[0]
    assert isinstance(outer, Initialize)
    assert isinstance(loop.condition.left, Reference)  # type: ignore[attr-defined]
    assert loop.condition.left.symbol is outer.symbol  # type: ignore[attr-defined]


def test_while_body_and_else_typed_declarations_and_existing_write() -> None:
    program = PythonFrontend().parse("""
count: int = 2
while count > 0:
    step: int = count
    count -= 1
    print(step)
else:
    done: str = 'finished'
    print(done)
print(count)
""")
    init, loop, _ = program.body.children
    assert isinstance(init, Initialize)
    assert isinstance(loop, While)
    assert isinstance(loop.body.children[0], Initialize)
    assert loop.else_body is not None
    assert isinstance(loop.else_body.children[0], Initialize)


def test_for_declared_target_and_implicit_target_both_allow_body_locals() -> None:
    program = PythonFrontend().parse("""
i: int = 0
for i in range(2):
    first: int = i
    print(first)
for j in range(3):
    second: int = j
    print(second)
""")
    existing = program.body.children[1]
    introduced = program.body.children[2]
    assert isinstance(existing, For)
    assert isinstance(introduced, For)
    assert not existing.entry.introduces_binding
    assert introduced.entry.introduces_binding
    assert isinstance(existing.body.children[0], Initialize)
    assert isinstance(introduced.body.children[0], Initialize)


def test_with_declarations_retained_in_body() -> None:
    program = PythonFrontend().parse("""
resource: int = 1
with resource:
    local: int = 2
    print(local)
""")
    context = program.body.children[1]
    assert isinstance(context, With)
    assert isinstance(context.body.children[0], Initialize)


def test_nested_function_uses_function_scope_and_control_local_body() -> None:
    program = PythonFrontend().parse("""
def f(flag: bool) -> int:
    total: int = 0
    if flag:
        addition: int = 3
        total = addition
    return total
""")
    definition = program.body.children[0]
    assert isinstance(definition, FunctionDefinition)
    branch = definition.body.children[1]
    assert isinstance(branch, Branch)
    init = branch.then_body.children[0]
    assert isinstance(init, Initialize)
    assert init.symbol.scope == ("f",)
    assert (
        definition.body.children[-1].value.symbol is definition.body.children[0].symbol
    )  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "source",
    [
        "flag: bool = False\nif flag:\n    x: int = 1\nprint(x)",
        "flag: bool = False\nif flag:\n    x: int = 1\nelse:\n    print(x)",
        "flag: bool = True\nif flag:\n    x: int = 1\n    print(x)\nprint(x)",
        "n: int = 2\nwhile n > 0:\n    x: int = n\n    n = n - 1\nprint(x)",
        "for i in range(2):\n    x: int = i\nelse:\n    print(x)",
        "for i in range(2):\n    x: int = i\nprint(x)",
        "resource: int = 1\nwith resource:\n    x: int = 2\nprint(x)",
        "flag: bool = True\nif flag:\n    x: int = 3\n    if flag:\n        y: int = 2\n    print(y)",
        "flag: bool = True\nif flag:\n    print(x)\n    x: int = 3",
    ],
)
def test_control_local_names_never_resolve_outside_or_before_declaration(
    source: str,
) -> None:
    with pytest.raises(UnsupportedPython):
        PythonFrontend().parse(source)


def test_lambda_cannot_capture_new_control_local_or_introduced_for_target() -> None:
    sources = [
        """
from typing import Callable
if True:
    x: int = 2
    f: Callable[[], int] = lambda: x
""",
        """
from typing import Callable
for i in range(3):
    f: Callable[[], int] = lambda: i
""",
    ]
    for source in sources:
        with pytest.raises(UnsupportedPython, match="Lambda capture"):
            PythonFrontend().parse(source)


def test_lambda_without_control_local_capture_still_allowed() -> None:
    program = PythonFrontend().parse("""
from typing import Callable
f: Callable[[], int] = lambda: 5
if True:
    g: Callable[[], int] = lambda: 6
""")
    assert isinstance(program.body.children[1], Branch)


def test_unsupported_mapping_and_exception_body_unchanged() -> None:
    with pytest.raises(UnsupportedPython, match="New bindings"):
        PythonFrontend().parse("""
try:
    local: int = 1
finally:
    pass
""")


def test_failed_parse_does_not_affect_frontend_reuse() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython):
        frontend.parse("if True:\n    local: int = 2\nprint(local)")
    program = frontend.parse("if True:\n    local: int = 3\n    print(local)")
    assert isinstance(program.body.children[0], Branch)
