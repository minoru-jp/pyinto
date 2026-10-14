"""SDD phase 2: separate the Construct Model parts from realization layouts."""

from __future__ import annotations

import ast

import pytest

from pyinto.constructs import (
    Block,
    ContextEntry,
    Identifier,
    Initialize,
    Literal,
    Program,
    Reference,
    Symbol,
    ValueKind,
    ValueType,
    With,
)
from pyinto.frontend import PythonFrontend
from pyinto.realizations.layout import Joined, Name, Requirements, TypeName
from pyinto.realizations.registry import Composer
from tests.model_sources import construct_trees
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def test_cst_007_basic_parts_never_leak_realization_nodes() -> None:
    n = Symbol("n", ValueType(ValueKind.INTEGER), "int")
    init = Initialize(n, Literal(2))
    program = Program(Block((init,)))
    assert Reference(n).parts() == {"name": Identifier("n")}
    assert init.parts() == {
        "name": Identifier("n"),
        "type": n,
        "value": Literal(2),
    }
    assert program.body.parts()["children"] == (init,)
    assert program.parts() == {"body": program.body}
    for construct in (Reference(n), init, program.body, program):
        for part in construct.parts().values():
            assert not isinstance(part, (Name, TypeName, Joined, Requirements))


def test_cst_008_with_preserves_order_not_separator() -> None:
    n = Symbol("n", ValueType(ValueKind.INTEGER), "int")
    a, b = ContextEntry(Reference(n)), ContextEntry(Reference(n))
    with_node = With((a, b), Block(()))
    assert with_node.parts() == {
        "entry0": a,
        "entry1": b,
        "body": with_node.body,
    }
    assert "entries" not in with_node.parts()


def test_cmp_008_both_targets_preserve_output_with_structural_parts() -> None:
    program = PythonFrontend().parse('n: int = 1\nprint("ok")')
    assert "long long n = 1LL;" in Composer(c_bindings()).source(program)
    assert "#include <stdio.h>" in Composer(c_bindings()).source(program)
    assert Composer(python_bindings()).source(program) == "n = 1\nprint('ok')\n"
    source = 'a: int = 1\nb: int = 2\nwith a, b:\n    print("ok")\n'
    text = Composer(python_bindings()).source(PythonFrontend().parse(source))
    assert "with a, b:" in text
    assert "    print('ok')" in text


def test_cmp_008_target_naming_still_applies_to_model_identifiers() -> None:
    symbol = Symbol("sk_bad", ValueType(ValueKind.INTEGER), "int")
    with pytest.raises(ValueError, match="Name is not portable"):
        Composer(c_bindings()).source(Program(Block((Initialize(symbol, Literal(1)),))))


def test_model_parts_are_resolved_without_binding_imports() -> None:
    # Source-level check of the dependency direction: no imports from the
    # realization subsystem inside core `parts()` implementations.
    part_methods = [
        item
        for module in construct_trees()
        for cls in module.body
        if isinstance(cls, ast.ClassDef)
        for item in cls.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == "parts"
    ]
    assert part_methods
    for method in part_methods:
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("pyinto.realizations")
            for node in ast.walk(method)
        )
