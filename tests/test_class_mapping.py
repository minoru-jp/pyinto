"""Class mappings: registered operations, alias typing and explicit cleanup."""

from __future__ import annotations

from pathlib import Path

import pytest
from shikumi_contrace import binds, upholds

from pyinto import PythonFrontend, UnsupportedPython, realize
from pyinto.constructs import Assign, Branch, Comparison, Initialize, Reference, While
from pyinto.contracts.boundaries.pipeline import FrontendBoundary
from pyinto.contracts.class_mapping_contract import ClassMappingContract
from tests.support.class_mapping import (
    IMPORT,
    CounterAdd,
    CounterClose,
    CounterOpen,
    CounterValue,
    c_counter_bindings,
    interface_mapping_registry,
)
from tests.test_construct_pipeline import run_c


def realize_mapping(program):
    return realize(
        program,
        realizations=c_counter_bindings(),
        admission=interface_mapping_registry().admission,
    )


def counter_source(*, close: bool = True, alias: bool = False) -> str:
    source = IMPORT + "a: Counter = Counter.open()\n"
    source += "b: Counter = a\nb.add(42)\n" if alias else "a.add(42)\n"
    source += "if a.value == 42:\n    print('ok')\n"
    if close:
        source += "a.close()\n"
    return source


def parse(source: str):
    return PythonFrontend(interface_mapping_registry()).parse(source)


@binds[FrontendBoundary](PythonFrontend)
class TestClassMapping:
    @upholds(ClassMappingContract.parse.ExplicitOperations)
    def test_construct_tree_preserves_registered_positions(self) -> None:
        p = parse(counter_source())
        opened, added, condition, closed = p.body.children
        assert isinstance(opened, CounterOpen)
        assert isinstance(added, CounterAdd)
        assert isinstance(condition, Branch)
        assert isinstance(condition.condition.left, CounterValue)
        assert isinstance(closed, CounterClose)
        assert closed.receiver.symbol is opened.symbol

    @upholds(ClassMappingContract.parse.NoImplicitCleanup)
    @pytest.mark.parametrize("close", [True, False])
    def test_cleanup_only_when_explicit(self, close: bool) -> None:
        produced = realize_mapping(parse(counter_source(close=close)))
        assert ("a = -1LL;" in produced) is close

    @upholds(ClassMappingContract.parse.AliasRepresentation)
    def test_alias_inherits_source_mapped_shape(self, tmp_path: Path) -> None:
        p = parse(counter_source(alias=True))
        alias = p.body.children[1]
        assert isinstance(alias, Initialize)
        assert isinstance(alias.value, Reference)
        assert alias.symbol.mapped_type == alias.value.symbol.mapped_type
        generated = realize_mapping(p)
        assert "long long b = a;" in generated

    @upholds(ClassMappingContract.parse.AliasRepresentation)
    def test_rebinding_same_mapped_shape(self) -> None:
        p = parse(
            IMPORT
            + "a: Counter = Counter.open()\nb: Counter = Counter.open()\n"
            + "b = a\nb.close()\na.close()\n"
        )
        assert isinstance(p.body.children[2], Assign)
        assert "b = a;" in realize_mapping(p)

    @upholds(ClassMappingContract.parse.StrictBoundary)
    @pytest.mark.parametrize(
        "source, match",
        [
            (IMPORT + "a = Counter.open()", "annotation"),
            (IMPORT + "a: int = Counter.open()", "directly imported"),
            (IMPORT + "a: Counter = unknown()", "registered constructor"),
            (IMPORT + "a: Counter = Counter.open(8)", "take no arguments"),
            (IMPORT + "a: Counter = Counter.open(size=8)", "take no arguments"),
            (IMPORT + "a: Counter = Counter.open()\na.unknown()", "object method"),
            (IMPORT + "a: Counter = Counter.open()\na.close(1)", "argument count"),
            (IMPORT + "a: Counter = Counter.open()\nb: int = a", "Annotated type"),
            (
                IMPORT + "a: Counter = Counter.open()\nb: Counter = a\nb = 1",
                "Variable type",
            ),
        ],
    )
    def test_reject_unsupported_mapping_semantics(
        self, source: str, match: str
    ) -> None:
        with pytest.raises(UnsupportedPython, match=match):
            parse(source)

    @upholds(ClassMappingContract.parse.NoImplicitCleanup)
    def test_operations_compile_and_run(self, tmp_path: Path) -> None:
        result = run_c(realize_mapping(parse(counter_source())), tmp_path)
        assert result.returncode == 0 and result.stdout == b"ok\n"

    @upholds(ClassMappingContract.parse.ExplicitOperations)
    def test_while_entry_can_use_mapped_value(self, tmp_path: Path) -> None:
        program = parse(
            IMPORT
            + "a: Counter = Counter.open()\n"
            + 'while a.value < 2:\n    print("tick")\n    a.add(1)\na.close()\n'
        )
        loop = program.body.children[1]
        assert isinstance(loop, While)
        assert isinstance(loop.condition, Comparison)
        code = realize_mapping(program)
        assert "while ((a < 2LL))" in code
        result = run_c(code, tmp_path)
        assert result.returncode == 0 and result.stdout == b"tick\ntick\n"
