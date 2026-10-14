"""SDD phase 3: conversion entry belongs to pyinto API, not to Model."""

from __future__ import annotations

import ast

import pytest
from demo_ports_pyinto import c_device_bindings, interface_mapping_registry

from pyinto import ConstructError, PythonFrontend, convert, realize
from pyinto.constructs import Program
from pyinto.frontend import UnsupportedPython
from pyinto.realizations.registry import RealizationRegistry
from tests.model_sources import construct_trees
from tests.support.c_realizer import c_bindings
from tests.support.python_realizer.pack import python_bindings


def test_cvt_001_explicit_pack_converts_source() -> None:
    code = 'n: int = 2\nprint("ok")'
    assert 'puts("ok")' in convert(code, realizations=c_bindings())
    assert convert(code, realizations=python_bindings()) == "n = 2\nprint('ok')\n"


def test_cvt_002_realize_reuses_unmodified_model() -> None:
    program = PythonFrontend().parse('print("again")')
    before = program.parts()
    c = realize(program, realizations=c_bindings())
    assert c == realize(program, realizations=c_bindings())
    assert realize(program, realizations=python_bindings()) == "print('again')\n"
    assert program.parts() == before
    assert 'puts("again")' in c


def test_cst_006_construct_has_no_realization_entry_or_dependencies() -> None:
    assert not hasattr(Program, "to_c")
    assert not hasattr(Program, "to_source")
    for module in construct_trees():
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(
                    ("pyinto.realizations", "pyinto.targets", "pyinto.api")
                )


def test_cvt_003_missing_dependencies_and_unregistered_ops_fail() -> None:
    with pytest.raises(TypeError, match="RealizationRegistry"):
        convert("print('hello')", realizations="c")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="RealizationRegistry"):
        realize(PythonFrontend().parse("print('ok')"), realizations="c")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="source must be a string"):
        convert(12, realizations=c_bindings())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="InterfaceMappingRegistry"):
        convert("print('ok')", realizations=c_bindings(), interface_mappings=object())  # type: ignore[arg-type]
    with pytest.raises(
        UnsupportedPython, match="Unregistered interface mapping import"
    ):
        convert("from demo_ports.device import is_ready", realizations=c_bindings())
    with pytest.raises(ConstructError, match="No 'c' realization"):
        convert("print('ok')", realizations=RealizationRegistry("c", ()))


def test_cvt_003_explicit_ports_are_handed_to_frontend() -> None:
    source = (
        "from demo_ports.device import is_ready\nif is_ready():\n    print('ready')\n"
    )
    result = convert(
        source,
        realizations=c_device_bindings(),
        interface_mappings=interface_mapping_registry(),
    )
    assert "device_is_ready()" in result
    assert "_force" not in result
