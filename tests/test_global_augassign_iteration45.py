"""Iteration 45: explicit global augmented rebinding and lexical name safety."""

# ruff: noqa: ISC004

from __future__ import annotations

import pytest

from pyinto.analysis import lexical_captures
from pyinto.constructs import (
    AugAssign,
    AugAssignMode,
    FunctionCall,
    FunctionDefinition,
    Initialize,
    Literal,
    Reference,
    Return,
    ValueKind,
)
from pyinto.constructs.admission import required_contracts
from pyinto.frontend import PythonFrontend, UnsupportedPython


def parse(source: str):
    return PythonFrontend().parse(source).body.children


def test_explicit_global_augassign_preserves_exact_module_symbol_and_contracts() -> (
    None
):
    declaration, update, invocation = parse(
        "counter: int = 0\n"
        "def increment() -> None:\n"
        "    global counter\n"
        "    counter += 1\n"
        "increment()\n"
    )
    assert isinstance(declaration, Initialize)
    assert isinstance(update, FunctionDefinition)
    assert len(update.body.children) == 1  # global is lexical, not executable
    operation = update.body.children[0]
    assert isinstance(operation, AugAssign)
    assert isinstance(operation.target, Reference)
    assert operation.target.symbol is declaration.symbol
    assert operation.target.symbol.scope == ()
    assert operation.mode is AugAssignMode.REBIND
    assert operation.operator == "+"
    assert operation.value == Literal(1)
    assert operation.parts()["target"] is operation.target
    assert required_contracts(operation) == {
        "assignment.augmented.target_once",
        "assignment.augmented.read_before_rhs",
        "assignment.augmented.rebind",
    }
    assert isinstance(invocation.value, FunctionCall)
    assert invocation.value.signature is update.signature
    assert lexical_captures(update) == ()


@pytest.mark.parametrize(
    ("annotation", "initializer", "operator", "rhs", "kind"),
    [
        ("int", "8", "+=", "2", ValueKind.INTEGER),
        ("int", "8", "-=", "2", ValueKind.INTEGER),
        ("int", "8", "*=", "2", ValueKind.INTEGER),
        ("int", "8", "//=", "2", ValueKind.INTEGER),
        ("int", "8", "%=", "3", ValueKind.INTEGER),
        ("int", "8", "&=", "3", ValueKind.INTEGER),
        ("int", "8", "<<=", "1", ValueKind.INTEGER),
        ("float", "8.0", "+=", "2.0", ValueKind.FLOAT),
        ("float", "8.0", "/=", "2.0", ValueKind.FLOAT),
    ],
)
def test_global_augassign_reuses_existing_scalar_operator_rules(
    annotation: str, initializer: str, operator: str, rhs: str, kind: ValueKind
) -> None:
    declaration, function = parse(
        f"value: {annotation} = {initializer}\n"
        "def update() -> None:\n"
        "    global value\n"
        f"    value {operator} {rhs}\n"
    )
    op = function.body.children[0]
    assert isinstance(op, AugAssign)
    assert isinstance(op.target, Reference)
    assert op.target.symbol is declaration.symbol
    assert op.target.kind is kind
    assert op.operator == operator[:-1]


def test_multiple_global_names_with_control_block_augassign() -> None:
    a, b, function = parse(
        "x: int = 1\n"
        "y: float = 2.0\n"
        "def update(flag: bool) -> None:\n"
        '    """Keep these bindings shared."""\n'
        "    global x, y\n"
        "    if flag:\n"
        "        x += 3\n"
        "    else:\n"
        "        y *= 2.0\n"
    )
    branch = function.body.children[0]
    first = branch.then_body.children[0]
    second = branch.else_body.children[0]
    assert function.docstring == "Keep these bindings shared."
    assert isinstance(first, AugAssign)
    assert isinstance(second, AugAssign)
    assert isinstance(first.target, Reference)
    assert isinstance(second.target, Reference)
    assert first.target.symbol is a.symbol
    assert second.target.symbol is b.symbol


def test_rhs_global_mutation_is_retained_as_call_not_evaluated_or_reordered() -> None:
    source = (
        "counter: int = 1\n"
        "def change() -> int:\n"
        "    global counter\n"
        "    counter = 10\n"
        "    return 2\n"
        "def update() -> None:\n"
        "    global counter\n"
        "    counter += change()\n"
    )
    declaration, changer, updater = parse(source)
    augmented = updater.body.children[0]
    assert isinstance(augmented, AugAssign)
    assert isinstance(augmented.target, Reference)
    assert augmented.target.symbol is declaration.symbol
    assert isinstance(augmented.value, FunctionCall)
    assert augmented.value.signature is changer.signature
    assert required_contracts(augmented) >= {
        "assignment.augmented.target_once",
        "assignment.augmented.read_before_rhs",
        "assignment.augmented.rebind",
    }
    # The frontend does not execute change(), or rewrite x += f() as x = x + f().


def test_local_augassign_uses_its_local_declaration_not_module_variable() -> None:
    global_declaration, function = parse(
        "counter: int = 0\n"
        "def update() -> int:\n"
        "    counter: int = 2\n"
        "    counter += 1\n"
        "    return counter\n"
    )
    local_declaration, augmented, returned = function.body.children
    assert isinstance(local_declaration, Initialize)
    assert isinstance(augmented, AugAssign)
    assert isinstance(augmented.target, Reference)
    assert augmented.target.symbol is local_declaration.symbol
    assert augmented.target.symbol is not global_declaration.symbol
    assert augmented.target.symbol.scope == ("update",)
    assert isinstance(returned, Return)
    assert returned.value.symbol is local_declaration.symbol


def test_parameter_augassign_remains_local_and_module_binding_unchanged() -> None:
    global_declaration, function = parse(
        "value: int = 10\n"
        "def update(value: int) -> int:\n"
        "    value += 1\n"
        "    return value\n"
    )
    augmented = function.body.children[0]
    assert isinstance(augmented, AugAssign)
    assert isinstance(augmented.target, Reference)
    assert augmented.target.symbol is function.signature.parameters[0]
    assert augmented.target.symbol is not global_declaration.symbol


@pytest.mark.parametrize(
    "statement",
    [
        "counter += 1",
        "counter -= 1",
        "counter <<= 1",
        "if True:\n        counter += 1",
        "counter += 1\ncounter: int = 10",
    ],
)
def test_implicit_module_augassign_does_not_resolve_outer_binding(
    statement: str,
) -> None:
    # Python binds the name locally across the whole function, even if the
    # only store is an AugAssign and even before a later typed declaration.
    with pytest.raises(UnsupportedPython):
        parse(
            "counter: int = 0\n"
            "def update() -> None:\n"
            + "\n".join("    " + line for line in statement.splitlines())
            + "\n"
        )


def test_name_reserved_by_augassign_blocks_earlier_read_from_module() -> None:
    with pytest.raises(UnsupportedPython, match="Unresolved name"):
        parse(
            "counter: int = 0\n"
            "def update() -> int:\n"
            "    earlier: int = counter\n"
            "    counter += 1\n"
            "    return earlier\n"
        )


def test_nested_function_augassign_without_nonlocal_does_not_mutate_outer() -> None:
    with pytest.raises(UnsupportedPython, match="declared name"):
        parse(
            "counter: int = 0\n"
            "def outer() -> None:\n"
            "    def inner() -> None:\n"
            "        counter += 1\n"
        )


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        (
            "counter: int = 0\n"
            "def f() -> None:\n    global counter\n    counter += 1.0\n",
            "Unsupported scalar",
        ),
        (
            "counter: float = 1.0\n"
            "def f() -> None:\n    global counter\n    counter //= 2.0\n",
            "Unsupported scalar",
        ),
        (
            "counter: str = 'a'\n"
            "def f() -> None:\n    global counter\n    counter += 'b'\n",
            "scalar int or float",
        ),
        (
            "counter: list[int] = [1]\n"
            "def f() -> None:\n    global counter\n    counter += [2]\n",
            "scalar int or float",
        ),
        (
            "counter: int = 1\n"
            "def f() -> None:\n    global counter\n    counter **= 2\n",
            "Unsupported augmented assignment operator",
        ),
        (
            "def f() -> None:\n    global counter\n    counter += 1\n"
            "counter: int = 0\n",
            "earlier typed module variable",
        ),
        (
            "counter: int = 0\n"
            "def f() -> None:\n    global counter\n    counter: int = 1\n"
            "    counter += 2\n",
            "cannot be redeclared",
        ),
    ],
)
def test_global_augassign_preserves_existing_fail_closed_boundaries(
    source: str, diagnostic: str
) -> None:
    with pytest.raises(UnsupportedPython, match=diagnostic):
        parse(source)


def test_failed_parse_does_not_leave_implicit_or_explicit_global_binding() -> None:
    frontend = PythonFrontend()
    with pytest.raises(UnsupportedPython, match="declared name"):
        frontend.parse("counter: int = 0\ndef failed() -> None:\n    counter += 1\n")
    assert frontend._context.names.global_names == set()
    assert frontend._context.names.enclosing_scopes == []
    new = frontend.parse(
        "counter: int = 0\ndef ok() -> None:\n    global counter\n    counter += 1\n"
    )
    assert isinstance(new.body.children[-1].body.children[0], AugAssign)
    assert frontend._context.names.global_names == set()
    assert frontend._context.names.enclosing_scopes == []


def test_c_target_remains_unable_to_realize_global_augassign() -> None:
    from pyinto import ConstructError, realize
    from tests.support.c_realizer import c_bindings

    program = PythonFrontend().parse(
        "counter: int = 0\n"
        "def update() -> None:\n"
        "    global counter\n"
        "    counter += 1\n"
    )
    with pytest.raises(ConstructError):
        realize(program, realizations=c_bindings())
