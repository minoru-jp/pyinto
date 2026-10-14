"""Target-author exports preserve existing Model identities and fail-closed rules."""

from __future__ import annotations

from pyinto import convert
from pyinto.constructs import (
    Absolute,
    Branch,
    Construct,
    Length,
    PrintValues,
    Range,
    Symbol,
    While,
)
from pyinto.constructs.types import ValueKind
from pyinto.interfaces import builtins as builtin
from pyinto.interfaces import language as lang
from pyinto.model import value_types as vt
from pyinto.realizations.registry import RealizationRegistry
from pyinto.realizations.regulation import realizes, template, type_name
from tests.support.c_realizer import c_bindings


def test_language_public_interface_reexports_the_exact_construct_classes() -> None:
    assert lang.While is While
    assert lang.Branch is Branch
    assert issubclass(lang.While, Construct)
    assert lang.Program.__module__ == "pyinto.constructs.control"
    assert "While" in lang.__all__
    assert not hasattr(lang, "PrintValues")


def test_builtin_public_interface_preserves_existing_semantic_classes() -> None:
    assert builtin.PrintValues is PrintValues
    assert builtin.Range is Range
    assert builtin.Length is Length
    assert builtin.Absolute is Absolute
    assert "Range" in builtin.__all__
    assert not hasattr(builtin, "While")


def test_model_value_type_exports_keep_existing_value_kinds() -> None:
    assert vt.Integer is ValueKind.INTEGER
    assert vt.String is ValueKind.STRING
    assert vt.Boolean is ValueKind.BOOLEAN
    assert vt.Floating is ValueKind.FLOAT
    assert vt.ValueType(vt.Integer).kind is ValueKind.INTEGER
    assert vt.PortType.__module__ == "pyinto.constructs.types"


def test_public_reexports_can_be_used_with_existing_shikumi_descriptors() -> None:
    @realizes(lang.While)
    class CWhile:
        template @= "while (${condition}) { ${body} }"

    @realizes(vt.Integer)
    class CInteger:
        type_name @= "long long"

    registry = RealizationRegistry("c-test", (CWhile, CInteger))
    assert (
        registry.type_name(Symbol("i", vt.ValueType(vt.Integer), "int")) == "long long"
    )


def test_public_exports_do_not_change_c_conversion() -> None:
    result = convert('n: int = 1\nprint("ok")', realizations=c_bindings())
    assert "puts(" in result
    assert "long long" in result
