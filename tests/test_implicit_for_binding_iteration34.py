"""Iteration 34: typed loop binding introduction without definite-assignment inference."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import (
    Assign,
    Block,
    ConstructError,
    For,
    Initialize,
    IterationEntry,
    Literal,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def get_for(source: str) -> For:
    program = PythonFrontend().parse(source)
    for node in program.body.children:
        if isinstance(node, For):
            return node
    raise AssertionError("expected loop")


@pytest.mark.parametrize(
    "source,expected",
    [
        ("for i in range(4):\n    i = 8", ValueType(ValueKind.INTEGER)),
        ("for c in 'ab':\n    c = 'x'", ValueType(ValueKind.STRING)),
        (
            "items: list[str] = ['a', 'b']\nfor x in items:\n    x = 'z'",
            ValueType(ValueKind.STRING),
        ),
        (
            "pair: tuple[int, int] = (1, 2)\nfor x in pair:\n    x = 5",
            ValueType(ValueKind.INTEGER),
        ),
    ],
)
def test_new_binding_type_from_known_element_shape(
    source: str, expected: ValueType
) -> None:
    node = get_for(source)
    assert node.entry.introduces_binding is True
    assert node.entry.target.value_type == expected
    body = node.body.children[0]
    assert isinstance(body, Assign)
    assert body.target.symbol == node.entry.target.symbol
    assert node.entry.target.symbol.scope == ()
    assert "iteration.binding.introduced" in LANGUAGE_ADMISSION.required_contracts(node)
    assert "iteration.binding.introduced" in LANGUAGE_ADMISSION.required_contracts(
        node.entry
    )


def test_existing_target_is_updated_and_not_redeclared() -> None:
    program = PythonFrontend().parse("i: int = 5\nfor i in range(3):\n    i = 1\ni = 9")
    before, node, after = program.body.children
    assert isinstance(before, Initialize)
    assert isinstance(node, For)
    assert isinstance(after, Assign)
    assert node.entry.introduces_binding is False
    assert node.entry.target.symbol is before.symbol
    assert after.target.symbol is before.symbol
    assert "iteration.binding.introduced" not in LANGUAGE_ADMISSION.required_contracts(
        node
    )
    assert "iteration.binding.introduced" not in LANGUAGE_ADMISSION.required_contracts(
        node.entry
    )
    # Both standard packs remain compatible with the previously admitted form.
    assert "for i in range(3):" in realize(node, realizations=python_bindings())
    assert "sk_range_" in realize(node, realizations=c_bindings())


def test_new_binding_has_no_synthetic_initializer_and_one_identity() -> None:
    program = PythonFrontend().parse("for i in range(2):\n    i = 99\n    print(i)")
    assert len(program.body.children) == 1
    node = program.body.children[0]
    assert isinstance(node, For)
    assert all(not isinstance(part, Initialize) for part in node.body.children)
    assert node.entry.target.symbol == node.body.children[0].target.symbol  # type: ignore[attr-defined]
    assert node.entry.parts() == {
        "target": node.entry.target,
        "iterable": node.entry.iterable,
    }
    assert not hasattr(node.entry, "initializer")


def test_nested_loop_introductions_do_not_escape_and_have_correct_owner() -> None:
    program = PythonFrontend().parse("""
def f() -> None:
    for outer in range(2):
        for inner in range(2):
            inner = outer
    return
""")
    function = program.body.children[0]
    outer = function.body.children[0]  # type: ignore[attr-defined]
    inner = outer.body.children[0]
    assert isinstance(outer, For)
    assert isinstance(inner, For)
    assert outer.entry.target.symbol.scope == ("f",)
    assert inner.entry.target.symbol.scope == ("f",)
    assert outer.entry.introduces_binding
    assert inner.entry.introduces_binding
    assert inner.body.children[0].value.symbol is outer.entry.target.symbol  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "source, message",
    [
        (
            "for i in range(0):\n    pass\nprint(i)",
            "[Uu]nknown|[Uu]ndeclared|Unresolved",
        ),
        ("for i in range(0):\n    pass\ni = 2", "type annotation"),
        (
            "for i in range(0):\n    pass\nelse:\n    print(i)",
            "[Uu]nknown|[Uu]ndeclared|Unresolved",
        ),
        (
            "pair: tuple[int, str] = (1, 's')\nfor i in pair:\n    pass",
            "one known element type",
        ),
        (
            "pair: tuple[()] = ()\nfor i in pair:\n    pass",
            "one known element type",
        ),
        ("for i in i:\n    pass", "[Uu]nknown|[Uu]ndeclared|Unresolved"),
        ("for print in range(2):\n    pass", "reserved name"),
        ("for i, j in range(2):\n    pass", "single iteration name"),
        (
            "for i in range(2):\n    temp: int = 4\nprint(temp)",
            "Unresolved name",
        ),
    ],
)
def test_rejects_out_of_scope_unknown_and_ambiguous_cases(
    source: str, message: str
) -> None:
    with pytest.raises(UnsupportedPython, match=message):
        PythonFrontend().parse(source)


def test_function_name_reservation_and_no_implicit_capture() -> None:
    source = """
for i in range(2):
    pass

def f() -> int:
    return i
"""
    with pytest.raises(UnsupportedPython):
        PythonFrontend().parse(source)


def test_target_packs_reject_introduced_binding_before_render() -> None:
    node = get_for("for i in range(3):\n    pass")
    for bindings in (python_bindings(), c_bindings()):
        with pytest.raises(ConstructError, match="iteration.binding.introduced"):
            realize(node, realizations=bindings)


def test_model_introduction_flag_is_validated() -> None:
    sym = Symbol("i", ValueType(ValueKind.INTEGER), "int")
    value = Reference(sym)
    entry = IterationEntry(
        value, get_for("for i in range(2):\n    pass").entry.iterable, True
    )
    assert entry.introduces_binding
    assert entry.target is value
    with pytest.raises(ConstructError, match="boolean"):
        IterationEntry(value, Literal("hello"), 1)  # type: ignore[arg-type]
    with pytest.raises(ConstructError, match="matching element type"):
        IterationEntry(value, Literal("hello"), True)
    with pytest.raises(FrozenInstanceError):
        entry.introduces_binding = False  # type: ignore[misc]
    assert For(entry, Block(())).entry is entry
