"""SDD phase 5: Model invariants and output-only slots are distinct."""

from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass

import pytest

from pyinto import PythonFrontend, realize
from pyinto.constructs import (
    Block,
    Construct,
    For,
    Literal,
    Program,
    Range,
    With,
)
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes, template
from tests.model_sources import construct_trees
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def test_cst_010_model_does_not_claim_output_requirements() -> None:
    program = Program(Block(()))
    assert program.parts() == {"body": program.body}
    assert Program.HOLES == frozenset({"body"})
    assert "requirements" not in vars(program)


def test_cmp_011_program_requirements_remain_a_composition_feature() -> None:
    @realizes(Program)
    class ProgramWithRequirements:
        template @= "${requirements}${body}"

    @realizes(Program)
    class ProgramWithUnknownSlot:
        template @= "${unknown}${body}"

    @realizes(Block)
    class NonProgramWithRequirements:
        template @= "${requirements}${children}"

    RealizationRegistry("test", (ProgramWithRequirements,))
    with pytest.raises(ValueError, match="unknown template hole"):
        RealizationRegistry("test", (ProgramWithUnknownSlot,))
    with pytest.raises(ValueError, match="unknown template hole"):
        RealizationRegistry("test", (NonProgramWithRequirements,))


@pytest.mark.parametrize("bad", [True, False, 1.5, None, b"hi", object()])
def test_cst_011_literal_rejects_unsupported_runtime_values(bad: object) -> None:
    with pytest.raises(ValueError, match="integer or string"):
        Literal(bad)  # type: ignore[arg-type]


def test_cst_011_literal_model_kind_is_not_target_dependent() -> None:
    assert Literal(0).kind.value == "integer"
    assert Literal("x").kind.value == "string"
    assert Literal(-1).variant() == "integer"


def _has_ast(value: object) -> bool:
    if isinstance(value, ast.AST):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_ast(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_has_ast(getattr(value, field.name)) for field in fields(value))
    return False


def test_cst_012_nested_model_survives_target_changes() -> None:
    code = "i: int = 0\nfor i in range(2):\n    if i == 0:\n        print('ok')\n"
    model = PythonFrontend().parse(code)
    assert isinstance(model.body.children[1], For)
    loop = model.body.children[1]
    assert isinstance(loop.entry.iterable, Range)
    assert not _has_ast(model)
    assert all(not hasattr(n, "to_source") for n in (model, loop))
    before = repr(model)
    c_source = realize(model, realizations=c_bindings())
    python_source = realize(model, realizations=python_bindings())
    assert "for (long long" in c_source
    assert "for i in range(2):" in python_source
    assert repr(model) == before
    assert realize(model, realizations=c_bindings()) == c_source


def test_cst_012_model_imports_no_realization_classes() -> None:
    assert all(
        not (
            isinstance(node, (ast.ImportFrom, ast.Import))
            and (getattr(node, "module", "") or "").startswith("pyinto.realizations")
        )
        for module in construct_trees()
        for node in ast.walk(module)
    )
    assert issubclass(With, Construct)
